import errno
import logging
import os
import shlex
import shutil
import subprocess
import time
from itertools import cycle
from pathlib import Path
from typing import Any, Optional

from .core import (
    Comparator,
    ComparisonResult,
    ComparisonStatus,
    CrashResult,
    FuzzVariable,
    InputFile,
    Project,
    Trace,
    TraceContext,
    TraceTemplate,
)

logger = logging.getLogger(__name__)


class ExecutorComparator(Comparator):
    """
    A dummy comparator class that is used when an internal trace comparison check fails.
    """

    id: str = '__executor__'

    def compare(self, original: Trace, debloated: Trace) -> ComparisonResult:
        return ComparisonResult.success(self, debloated)

    def verify_original(self, original: Trace) -> Optional[CrashResult]:
        pass


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
        logger.debug('running trace context: %s', context.id)
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
        if trace.timed_out and not trace.context.template.timeout.expected:
            return CrashResult(trace, 'Process was terminated because of an unexpected timeout')

        if not trace.timed_out and trace.context.template.timeout.expected:
            return CrashResult(trace, 'Process was expected to time out but exited early')

        crash = trace.crash_result
        if crash and not trace.timed_out:
            # An expected timeout will have a signal of SIGTERM because we had to terminate the
            # process. So, we only return a crash result on a signal if the process didn't timeout.
            return crash

        return None

    def run_trace(self, project: Project, trace: Trace) -> None:
        """
        Run a single trace.
        """
        logger.debug('running trace for context %s: %s', trace.context.id, trace.debloater_engine)
        hooks = list(trace.context.template.hooks)

        self.copy_input_files(trace)

        # Run setup hooks
        for hook in hooks:
            hook.setup(trace)

        stdin_file = self.create_stdin_file(trace)
        setup, teardown = self.write_hook_scripts(trace)

        if project.link_filename:
            link = trace.cwd / project.link_filename
            link.symlink_to(trace.binary)
            target = f'./{project.link_filename}'
        else:
            target = f'./{trace.binary.name}'

        cwd = trace.cwd.parent / 'current_trace'
        if cwd.exists():
            cwd.unlink()

        cwd.symlink_to(trace.cwd)

        if setup:
            # Run the trace setup script
            logger.debug(
                'running trace setup for context %s: %s', trace.context.id, trace.debloater_engine
            )
            subprocess.run([str(setup)], cwd=str(cwd))

        args = [target] + shlex.split(trace.context.arguments)
        trace.process = subprocess.Popen(
            args,
            cwd=str(cwd),
            stdout=trace.stdout_path.open('wb'),
            stderr=trace.stderr_path.open('wb'),
            stdin=stdin_file.open('rb'),
        )

        running = True
        status = 0
        end_time = time.monotonic() + trace.context.template.timeout.seconds
        while running and time.monotonic() < end_time:
            time.sleep(0.001)  # copied from subprocess.wait
            pid, status = os.waitpid(trace.process.pid, os.WNOHANG)
            running = pid != trace.process.pid  # pid will be "0" if the process is still running

        if running:
            # timeout reached
            logger.warning(
                'process reached timeout; terminating: %s: %s',
                trace.context.id,
                trace.debloater_engine,
            )
            trace.process.terminate()
            _, status = os.waitpid(trace.process.pid, 0)
            trace.timed_out = True

        trace.process_status = status
        trace.process.returncode = os.waitstatus_to_exitcode(status)
        logger.debug('process exited with code %d', trace.process.returncode)

        # Run teardown hooks
        for hook in hooks:
            hook.teardown(trace)

        if teardown:
            # Run the trace teardown script
            logger.debug(
                'running trace teardown for context %s: %s',
                trace.context.id,
                trace.debloater_engine,
            )
            subprocess.run([str(teardown)], cwd=str(cwd))

        cwd.unlink()

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
        logger.debug(
            'comparing results for trace context %s: %s',
            original.context.id,
            debloated.debloater_engine,
        )
        for comparator in comparators:
            result = comparator.compare(original, debloated)
            logger.debug('comparator %s result: %s', comparator.id, result.status.value)

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
        logger.debug(
            'creating trace for context %s: %s (%s)', context.id, binary, debloater_engine
        )
        cwd = project.trace_directory(context, debloater_engine)
        if cwd.exists():
            raise FileExistsError(errno.EEXIST, os.strerror(errno.EEXIST), str(cwd))

        cwd.mkdir()

        # symlink the binary to the trace directory
        link = cwd / binary.name
        link.symlink_to(binary)
        trace = Trace(link, context, cwd, debloater_engine)

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
            args = self.generate_arguments(template, values)
            contexts.append(TraceContext(template, args, values, id=f'{template.id}-{id:03}'))

        logger.debug('generated %d trace contexts for template %s', len(contexts), template.id)
        return contexts

    def generate_arguments(self, template: TraceTemplate, values: dict) -> str:
        """
        Generate the command line arguments using the provided variable values.

        :param template: trace template
        :param value: variable values
        :returns: the generated command line arguments
        """
        return template.arguments_template.render(**values)

    def generate_parameters(self, template: TraceTemplate) -> list[dict]:
        """
        Generate the concrete values for the trace template variables. This runs each variable's
        :meth:`~FuzzVariable.generate_values`.

        :param template: trace template
        :returns: a list of generated variable values
        """
        generators = [
            VariableValueGenerator(template, variable) for variable in template.variables.values()
        ]
        names = [item.variable.name for item in generators]
        count = 0
        done = False
        values: list[dict] = []

        while not done:
            # Populate a dictionary of the generated values
            values.append({name: next(generator) for name, generator in zip(names, generators)})
            count += 1
            # We are done when every variable has been exhausted or the number of value sets
            # generated is greater than the max_permutations setting.
            done = (
                all(generator.exhausted for generator in generators)
                or count >= self.max_permutations
            )

        logger.debug('generated %d value sets for template %s', len(values), template.id)
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
        logger.debug(
            'generating input file for trace %s: %s', trace.debloater_engine, input_file.source
        )
        dest = input_file.get_destination(trace.cwd)
        if not dest.parent.exists():
            dest.parent.mkdir(parents=True)

        content = input_file.template.render(**trace.context.values)
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
                content = template.render(**trace.context.values)
                file.write(content.encode())

        return filename

    def write_hook_scripts(self, trace: Trace) -> tuple[Optional[Path], Optional[Path]]:
        """
        Generate Bash scripts for trace setup and teardown. If the hook has not body then the item
        within the tuple is ``None``.

        :returns: a tuple containing the paths to the ``setup`` and ``teardown`` scripts to execute
        """
        templates = [
            (trace.context.template.setup_template, trace.setup_script_path),
            (trace.context.template.teardown_template, trace.teardown_script_path),
        ]
        scripts: list[Optional[Path]] = []
        for template, filename in templates:
            if not template:
                scripts.append(None)
                continue

            with open(filename, 'w') as file:
                print('#!/bin/bash', file=file)
                print(template.render(**trace.context.values), file=file)

            os.chmod(filename, 0o755)
            scripts.append(filename)

        return tuple(scripts)


class VariableValueGenerator:
    """
    An iterator that produces generated values for a variable. The generated values are cached so
    that the iterator does not need to be recreated when it has been exhausted. The iterator will
    produce results forever, callers should check if the iterator has been exhausted using the
    ``exhausted`` attribute.
    """

    def __init__(self, template: TraceTemplate, variable: FuzzVariable):
        self.variable = variable
        self._iter = variable.generate_values(template)
        self._current = next(self._iter)
        self._values = []
        self.exhausted = False

    def __next__(self) -> Any:
        value = self._current
        try:
            self._current = next(self._iter)
        except StopIteration:
            # Iterator has been exhausted, we now produce values from the cache
            self.exhausted = True
            self._iter = cycle(self._values)
            self._current = next(self._iter)
        else:
            # Cache the value
            self._values.append(value)

        return self._current
