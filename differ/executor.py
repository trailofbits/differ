import errno
import logging
import os
import shlex
import shutil
import signal
import subprocess
import time
from pathlib import Path
from typing import Optional

from .core import (
    Comparator,
    ComparisonResult,
    ComparisonStatus,
    ConcurrentHookMode,
    CrashResult,
    InputFile,
    Project,
    Trace,
    TraceContext,
    TraceTemplate,
)
from .parameters import CombinationParameterGenerator
from .template import JINJA_ENVIRONMENT

logger = logging.getLogger(__name__)

SCRIPT_RETRY_TEMPLATE = JINJA_ENVIRONMENT.from_string(
    """
cycle=0
while [ $cycle -lt {{retries}} ];
do
  if [ ! {{script}} ];
  then
    # the script was successful, exit
    exit 0
  fi

  # The script failed, sleep and retry
  sleep {{delay}}
  ((cycle++))
done

# One final attempt, keeping the exit code from the script
{{script}}
"""
)


class ExecutorComparator(Comparator):
    """
    A dummy comparator class that is used when an internal trace comparison check fails.
    """

    id: str = '__executor__'

    def compare(self, original: Trace, debloated: Trace) -> ComparisonResult:
        return ComparisonResult.success(self, debloated)  # pragma: no cover

    def verify_original(self, original: Trace) -> Optional[CrashResult]:
        pass    # pragma: no cover


#: Singleton for the executor comparator
EXECUTOR_COMPARATOR = ExecutorComparator({})


class Executor:
    """
    Project executor that executes an entire project and produces a report of results.
    """

    def __init__(
        self,
        root: Path,
        max_permutations: int = 100,
        report_successes: bool = False,
        verbose: bool = False,
        overwrite_existing_report: bool = False,
    ):
        """
        :param root: root directory to store results
        :param max_permutations: the maximum number of parameter permutations to execute for a
            single trace
        :param report_successes: report comparison successes
        :param verbose: verbose log output
        """
        self.root = root.absolute()
        self.max_permutations = max_permutations
        self.report_successes = report_successes
        self.verbose = verbose
        self.overwrite_existing_report = overwrite_existing_report

    def setup(self) -> None:
        """
        Setup the executor. This method must be called prior to loading or running any projects.
        """
        from .comparators import load_comparators
        from .variables import load_variables

        load_comparators()
        load_variables()

        logging.basicConfig(
            level=logging.DEBUG if self.verbose else logging.INFO,
            format='[%(asctime)s] %(levelname)s %(name)s %(message)s',
            datefmt='%H:%M:%S',
        )

        if not self.root.exists():
            self.root.mkdir()

    def run_project(self, project: Project) -> int:
        """
        Run a project.

        :param project: the project
        """
        logger.info('running project: %s', project.name)
        if project.directory.exists():
            if not self.overwrite_existing_report:
                # The project directory must not exist
                raise FileExistsError(
                    errno.EEXIST, os.strerror(errno.EEXIST), str(project.directory)
                )
            shutil.rmtree(project.directory)

        project.directory.mkdir()

        error_count = 0
        context_count = 0
        for template in project.templates:
            contexts = self.generate_contexts(project, template)
            for context in contexts:
                context_count += 1
                error_count += self.run_context(project, context)

        trace_count = context_count * (len(project.debloaters) + 1)
        if not error_count:
            logger.info('project %s ran %d traces successfully', project.name, trace_count)
        else:
            logger.error(
                'project %s ran %d traces with %d errors', project.name, trace_count, error_count
            )

        return error_count

    def run_context(self, project: Project, context: TraceContext) -> int:
        """
        Run a trace context against the original binary and each debloated binary.
        """
        logger.debug('running trace context: %s', context)
        context_dir = project.context_directory(context)
        if context_dir.exists():
            raise FileExistsError(errno.EEXIST, os.strerror(errno.EEXIST), str(context_dir))

        context_dir.mkdir()

        # First, run the original trace and verify it worked as expected
        original_trace = self.create_trace(project, context, project.original, '__original__')
        self.run_trace(project, original_trace)
        if crash := self.check_original_trace(project, original_trace):
            # The original did not behave as we expected and we can't trust the results of the
            # debloated binaries. Report the crash and quit.
            crash.save(project.crash_filename(original_trace))
            return 1

        error_count = 0
        # Run each debloated binary and compare it against the original
        for debloater in project.debloaters.values():
            trace = self.create_trace(project, context, debloater.binary, debloater.engine)
            self.run_trace(project, trace)

            results = self.compare_trace(project, original_trace, trace)
            crash = self.check_trace_crash(trace)
            errors = self.get_errors(trace, results, crash)

            # A crash is an error if we don't expect it (expect_success: true)
            crash_is_error = crash and trace.context.template.expect_success
            if not crash_is_error:
                # ignore the crash, it was expected
                crash = None

            if errors or crash:
                # update the error count
                error_count += 1

            reports = results if self.report_successes else errors
            if reports:
                project.save_report(trace, reports)

            if crash:
                crash.save(project.crash_filename(trace))

        return error_count

    def get_errors(
        self, trace: Trace, results: list[ComparisonResult], crash: Optional[CrashResult]
    ) -> list[ComparisonResult]:
        """
        Get the list of errors for the trace, honoring the template's ``expect_success``
        configuration. When ``expect_success: false``, the trace will fail if there are not errors
        and the trace did not crash.
        """
        errors = [item for item in results if not item]
        if trace.context.template.expect_success:
            # We expected the trace to be successful, return the list of errors
            return errors

        # We expected the trace to fail, determine if the trace was actually successful by failing
        if errors or crash:
            # The trace failed as we expected, flip all errors to successful and clear the error
            # list
            for err in errors:
                err.status = ComparisonStatus.success
                err.details += ' (expected error treated as success)'

            errors = []
        else:
            # The trace didn't fail, which is unexpected. Add a new error so it'll be reported
            error = ComparisonResult.error(
                EXECUTOR_COMPARATOR, trace, 'trace was expected to fail but did not'
            )
            results.append(error)
            errors = [error]

        return errors

    def check_original_trace(self, project: Project, trace: Trace) -> Optional[CrashResult]:
        """
        Check that the original trace behaved as expected and return a ``CrashResult`` if the
        original trace deviated from expected output or crashed.

        :param trace: original binary trace
        """
        if crash := self.check_trace_crash(trace):
            return crash

        for comparator in trace.context.template.comparators:
            if crash := comparator.verify_original(trace):
                return crash
        return None

    def check_trace_crash(self, trace: Trace) -> Optional[CrashResult]:
        """
        Check if the trash crashed and return a ``CrashResult`` if it did.
        """
        # Check if we timed out in an expected way
        if trace.timed_out and not trace.context.template.timeout.expected:
            return CrashResult(trace, 'Process was terminated because of an unexpected timeout')

        # Check if we expected to time out but didn't
        if not trace.timed_out and trace.context.template.timeout.expected:
            return CrashResult(trace, 'Process was expected to time out but exited early')

        crash = trace.crash_result
        if not crash or trace.timed_out:
            # The trace didn't crash or it timed out expectedly
            return None

        crash_signal = trace.crash_signal

        # Check if we crash in an expected way
        if crash_signal and trace.context.template.expect_signal == crash_signal.value:
            return None

        if concurrent := trace.context.template.concurrent:
            if concurrent.mode is ConcurrentHookMode.client and crash_signal is signal.SIGINT:
                # Check if the the concurrent client sent SIGINT to the trace
                return None

        return crash

    def run_trace(self, project: Project, trace: Trace) -> None:
        """
        Run a single trace.
        """
        logger.debug('running trace: %s', trace)

        # copy and generate any input files
        self.copy_input_files(trace)

        # create the file used for stdin
        stdin_file = self.create_stdin_file(trace)
        # generate the setup and teardown scripts, if specified
        self.write_hook_scripts(trace)

        if project.link_filename:
            # link the binary to the link_filename
            link = trace.cwd / project.link_filename
            link.symlink_to(trace.binary)
            target = f'./{project.link_filename}'
        else:
            target = f'./{trace.binary.name}'

        # link the 'current_trace' directory to the trace cwd so that paths are uniform
        cwd = trace.cwd.parent / 'current_trace'
        if cwd.exists():
            cwd.unlink()

        cwd.symlink_to(trace.cwd)

        # run setup hooks and setup script
        self._setup_trace(trace, cwd)

        # start the binary
        args = [target] + shlex.split(trace.arguments)
        trace.process = subprocess.Popen(
            args,
            cwd=str(cwd),
            stdout=trace.stdout_path.open('wb'),
            stderr=trace.stderr_path.open('wb'),
            stdin=stdin_file.open('rb'),
        )

        # monitor the process and launch the concurrent script
        self._monitor_trace(trace, cwd)

        # run the teardown hooks, teardown script, and terminate the concurrent script
        self._teardown_trace(trace, cwd)

        cwd.unlink()

    def _setup_trace(self, trace: Trace, cwd: Path) -> None:
        """
        Run the trace setup hooks and the setup script.
        """
        for hook in trace.context.template.hooks:
            hook.setup(trace)

        if not trace.setup_script_path.exists():
            return

        # Run the trace setup script
        logger.debug('running trace setup %s', trace)
        trace.setup_script = subprocess.run(
            [f'./{trace.setup_script_path.name}'],
            cwd=str(cwd),
            stdout=trace.setup_script_output.open('wb'),
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            env=trace.env(inherit=True),
        )

    def _teardown_trace(self, trace: Trace, cwd: Path) -> None:
        """
        Run the trace teardown hooks, the teardown script, and terminate the concurrent script if
        it is still running.
        """
        # Run teardown hooks
        for hook in trace.context.template.hooks:
            hook.teardown(trace)

        if trace.teardown_script_path.exists():
            # Run the trace teardown script
            logger.debug('running trace teardown %s: %s', trace)
            trace.teardown_script = subprocess.run(
                [f'./{trace.teardown_script_path.name}'],
                cwd=str(cwd),
                stdout=trace.teardown_script_output.open('wb'),
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                env=trace.env(inherit=True),
            )

        if trace.concurrent_script:
            # Determine how long we'll wait for the concurrent script to complete. Either the
            # remaining timeout amount for a minimum for 5 seconds.
            wait_time = float(trace.context.template.timeout.seconds) - (
                time.monotonic() - trace.start_time
            )
            if wait_time < 5.0:
                wait_time = 5.0
            try:
                trace.concurrent_script.wait(wait_time)
            except subprocess.TimeoutExpired:
                logger.error('terminating trace concurrent script: %s', trace)
                trace.concurrent_script.terminate()
                trace.concurrent_script.wait()

    def _monitor_trace(self, trace: Trace, cwd: Path) -> None:
        """
        Monitor the trace as it is running and block until it either finishes execution or the
        trace times out and is terminated by differ.
        """
        assert trace.process, 'trace process is not active'

        running = True
        status = 0
        trace.start_time = time.monotonic()
        end_time = trace.start_time + float(trace.context.template.timeout.seconds)

        if concurrent := trace.context.template.concurrent:
            concurrent_delay_time = trace.start_time + concurrent.delay
        else:
            concurrent_delay_time = 0.0

        initial_timeout = concurrent_delay_time or end_time
        if initial_timeout > trace.start_time:
            running, status = self._wait_process(trace.process, concurrent_delay_time or end_time)

        if running and concurrent_delay_time:
            trace.concurrent_script = subprocess.Popen(
                [f'./{trace.concurrent_script_path.name}'],
                cwd=str(cwd),
                stdout=trace.concurrent_script_output.open('wb'),
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                env=trace.env(inherit=True),
            )

            running, status = self._monitor_concurrent_mode(trace, end_time)

        if running:
            # timeout reached
            logger.warning('process reached timeout; terminating: %s', trace)
            trace.process.terminate()
            _, status = os.waitpid(trace.process.pid, 0)
            trace.timed_out = True

        trace.process_status = status
        trace.process.returncode = os.waitstatus_to_exitcode(status)
        logger.debug('process exited with code %s: %d', trace, trace.process.returncode)

    def _wait_process(self, process: subprocess.Popen, end_time: float) -> tuple[bool, int]:
        """
        Wait for the process to finish executing or until the ``end_time`` is surpassed.

        :param process: the subprocess to wait for
        :param end_time: the moment in time to wait until
        :returns: a tuple containing ``(is_still_running, wait_status)``
        """
        running = True
        status = 0
        while running and time.monotonic() < end_time:
            time.sleep(0.001)  # copied from subprocess.wait
            pid, status = os.waitpid(process.pid, os.WNOHANG)
            # pid will be "0" if the process is still running
            running = pid != process.pid

        return running, status

    def _monitor_concurrent_mode(self, trace: Trace, end_time: float) -> tuple[bool, int]:
        """
        Monitor the trace honoring the concurrent script mode. The return value of this method is
        the same as :meth:`_wait_process`.

        :param trace: the trace to monitor
        :param end_time: the moment in time to wait until
        :returns: a tuple containing ``(is_still_running, wait_status)``
        """
        config = trace.context.template.concurrent

        assert config, 'no concurrent script configuration set'  # pragma: no cover

        if not config.mode:
            assert trace.process  # pragma: no cover
            # no mode, wait for the trace to complete
            return self._wait_process(trace.process, end_time)

        if config.mode is ConcurrentHookMode.client:
            # client mode: wait for the concurrent script to complete
            return self._monitor_concurrent_client(trace, end_time)

        raise TypeError(f'unsupported concurrent script mode: {config.mode.name}')

    def _monitor_concurrent_client(self, trace: Trace, end_time: float) -> tuple[bool, int]:
        """
        Monitor the trace client. The return value of this method is the same as
        :meth:`_wait_process`.

        :param trace: the trace to monitor
        :param end_time: the moment in time to wait until
        :returns: a tuple containing ``(is_still_running, wait_status)``
        """
        config = trace.context.template.concurrent

        assert config, 'No concurrent configuration set'  # pragma: no cover
        assert trace.concurrent_script, 'Concurrent script is not running'  # pragma: no cover
        assert trace.process, 'Trace is not running'  # pragma: no cover

        # In client mode, we wait for the concurrent script to complete instead of the trace
        # process.
        client_running, client_status = self._wait_process(trace.concurrent_script, end_time)

        if not client_running:
            logger.debug('client has completed for trace: %s', trace)
            # In client mode, the trace process is terminated when the concurrent script completes.
            # Set the concurrent script exit code
            trace.concurrent_script.returncode = os.waitstatus_to_exitcode(client_status)

            # We allow the main process the delay_time to exit on its own before we terminate it.
            delay_end_time = time.monotonic() + config.delay
            running, status = self._wait_process(trace.process, delay_end_time)

            if running:
                logger.debug('terminating trace with SIGINT: %s', trace)
                # The trace is still running, now we terminate it
                trace.process.send_signal(signal.SIGINT.value)
                # Allow the process 5 seconds to cleanly exit
                return self._wait_process(trace.process, time.monotonic() + 5.0)
            else:
                # The trace completed on its own
                return running, status

        # The client is still running, check to see if the trace process has terminated
        return self._wait_process(trace.process, time.monotonic() + 1.0)

    def compare_trace(
        self, project: Project, original: Trace, debloated: Trace
    ) -> list[ComparisonResult]:
        """
        Compare a debloated trace against the original and return a comparison result for each
        comparator. This method will always return all comparison results.

        :param original: the trace of the original binary
        :param debloated: the trace of the debloated binary
        :returns: the list of comparison results
        """
        comparators = original.context.template.comparators
        results = []
        logger.debug('comparing results for trace %s', debloated)
        for comparator in comparators:
            result = comparator.compare(original, debloated)
            logger.debug(
                'comparator %s result for trace %s: %s',
                comparator.id,
                debloated,
                result.status.value,
            )

            results.append(result)

        return results

    def create_trace(
        self, project: Project, context: TraceContext, binary: Path, debloater_engine: str
    ) -> Trace:
        """
        Create a trace for a single binary. This creates the trace directory and links the binary
        into the trace directory.

        :param project: differ project
        :param context: trace context with generated variable values
        :param binary: binary to execute
        :param debloater_engine: debloater engine name
        :returns: the created trace object
        """
        logger.debug('creating trace %s[%s]: %s', context.id, debloater_engine, binary)
        cwd = project.trace_directory(context, debloater_engine)
        if cwd.exists():
            raise FileExistsError(errno.EEXIST, os.strerror(errno.EEXIST), str(cwd))

        cwd.mkdir()

        # symlink the binary to the trace directory
        link = cwd / binary.name
        link.symlink_to(binary)

        trace = Trace(link, context, cwd, debloater_engine)
        trace.arguments = context.template.arguments_template.render(trace=trace, **context.values)

        return trace

    def generate_contexts(self, project: Project, template: TraceTemplate) -> list[TraceContext]:
        """
        Generate a list of trace contexts with concrete variable values for the provided template.

        :param project: differ project
        :param template: trace template
        :returns: a list of trace contexts
        """
        contexts = []
        for id, values in enumerate(self.generate_parameters(template), start=1):
            contexts.append(TraceContext(template, values, id=f'{template.id}-{id:03}'))

        logger.debug('generated %d trace contexts for template %s', len(contexts), template)
        return contexts

    def generate_parameters(self, template: TraceTemplate) -> list[dict]:
        """
        Generate the concrete values for the trace template variables. This runs each variable's
        :meth:`~FuzzVariable.generate_values`.

        :param template: trace template
        :returns: a list of generated variable values
        """
        generator = CombinationParameterGenerator(template)
        count = 0
        values: list[dict] = []

        for parameters in generator.generate():
            # Populate a dictionary of the generated parameters
            values.append(parameters)
            count += 1
            # We are done when every variable has been exhausted or the number of parameters
            # generated is greater than the max_permutations setting.
            if count >= self.max_permutations:
                break

        logger.debug('generated %d parameters for template %s', len(values), template)
        return values

    def copy_input_files(self, trace: Trace) -> None:
        """
        Copy input files from the template to the trace.
        """
        for input_file in trace.context.template.input_files:
            if input_file.static:
                # This is a static file that should not be modified
                dest = input_file.get_destination(trace.cwd)
                if input_file.source.is_dir():
                    shutil.copytree(input_file.source, dest)
                else:
                    if not dest.parent.exists():
                        dest.parent.mkdir(parents=True)

                    shutil.copy(str(input_file.source), str(dest))
                    self.set_input_file_mode(input_file, dest)
            else:
                self.generate_input_file(trace, input_file)

    def generate_input_file(self, trace: Trace, input_file: InputFile) -> None:
        """
        Render an input file with the trace context variable values.
        """
        logger.debug('generating input file for trace %s: %s', trace, input_file.source)
        dest = input_file.get_destination(trace.cwd)
        if not dest.parent.exists():
            dest.parent.mkdir(parents=True)

        content = input_file.template.render(trace=trace, **trace.context.values)
        with open(dest, 'w') as file:
            file.write(content)

        self.set_input_file_mode(input_file, dest)

    def set_input_file_mode(self, input_file: InputFile, destination: Path) -> None:
        """
        Set the copied input file mode.
        """
        if not input_file.mode:
            # copy source file mode
            perms = input_file.source.stat().st_mode & 0o777
        else:
            perms = int(input_file.mode, 8)

        os.chmod(destination, perms)

    def create_stdin_file(self, trace: Trace) -> Path:
        """
        Create the standard input file for a trace. This methods returns the file that contains
        the standard input that can be piped into the trace subprocess. If the trace template
        ``stdin`` is a Path, then the resolved path is returned. Otherwise, a new stdin file is
        generated for the trace and returned.

        :returns: the path to the standard input file
        """
        stdin = trace.context.template.stdin
        if isinstance(stdin, Path):
            # This is a path, which can either be an input file that is generated or any file on
            # disk. We resolve the file against the trace working directory if it is relative.
            if not stdin.is_absolute():
                stdin = (trace.cwd / stdin).resolve()
            return stdin

        # stdin is either empty or a string that we need to generate based on the context values
        filename = trace.default_stdin_path
        with open(filename, 'wb') as file:
            if template := trace.context.template.stdin_template:
                content = template.render(trace=trace, **trace.context.values)
                file.write(content.encode())

        return filename

    def write_hook_scripts(self, trace: Trace) -> None:
        """
        Generate Bash scripts for trace setup and teardown. If the hook has not body then the item
        within the tuple is ``None``.

        :returns: a tuple containing the paths to the ``setup`` and ``teardown`` scripts to execute
        """
        templates = [
            (trace.context.template.setup_template, trace.setup_script_path, trace.context.values),
            (
                trace.context.template.teardown_template,
                trace.teardown_script_path,
                trace.context.values,
            ),
        ]

        # The concurrent script may be called multiple times if the concurrent.retries setting is
        # enabled. When enabled, we generate the concurrent script to a separate bash file that is
        # called repeatedly by the concurrent script.
        concurrent_body_path = trace.concurrent_script_path
        concurrent = trace.context.template.concurrent
        if concurrent and concurrent.retries:
            # we need to retry the concurrent script. Write the concurrent script to a different
            # file that the main script will run multiple times.
            concurrent_body_path = concurrent_body_path.with_suffix('.body.sh')
            kwargs = {
                'retries': concurrent.retries,
                'script': f'./{concurrent_body_path.name}',
                'delay': concurrent.delay,
            }
            templates.append((SCRIPT_RETRY_TEMPLATE, trace.concurrent_script_path, kwargs))

        templates.append(
            (
                trace.context.template.concurrent_template,
                concurrent_body_path,
                trace.context.values,
            )
        )

        for template, filename, values in templates:
            if not template:
                continue

            with open(filename, 'w') as file:
                print('#!/bin/bash', file=file)
                print(template.render(trace=trace, **values), file=file)

            os.chmod(filename, 0o755)
