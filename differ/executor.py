import errno
import logging
import os
import shlex
import subprocess
from itertools import cycle
from pathlib import Path
from typing import Any, Optional

from .core import (
    ComparisonResult,
    CrashResult,
    FuzzVariable,
    Project,
    Trace,
    TraceContext,
    TraceTemplate,
)

logger = logging.getLogger(__name__)


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

    def run_project(self, project: Project) -> None:
        """
        Run a project.

        :param project: the project
        """
        logger.info('running project: %s', project.name)
        if project.directory.exists():
            # The project directory must not exist
            raise FileExistsError(errno.EEXIST, os.strerror(errno.EEXIST), str(project.directory))

        project.directory.mkdir()

        for template in project.templates:
            contexts = self.generate_contexts(project, template)
            for context in contexts:
                self.run_context(project, context)

    def run_context(self, project: Project, context: TraceContext) -> None:
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
            crash.save(project.crash_filename(context))
            return

        # Run each debloated binary and compare it against the original
        for debloater in project.debloaters.values():
            trace = self.create_trace(project, context, debloater.binary, debloater.engine)
            self.run_trace(project, trace)
            if results := self.compare_trace(project, original_trace, trace):
                # Results will not be empty if there were failures or report_successes is True.
                project.save_report(trace, results)

    def check_original_trace(self, project: Project, trace: Trace) -> Optional[CrashResult]:
        """
        Check that the original trace behaved as expected and return a ``CrashResult`` if the
        original trace deviated from expected output.

        :param trace: original binary trace
        """
        for comparator in trace.context.template.comparators:
            if crash := comparator.verify_original(trace):
                return crash
        return None

    def run_trace(self, project: Project, trace: Trace) -> None:
        """
        Run a single trace.
        """
        logger.debug('running trace for context %s: %s', trace.context.id, trace.debloater_engine)
        hooks = list(trace.context.template.hooks)

        # Run setup hooks
        for hook in hooks:
            hook.setup(trace)

        args = [str(trace.binary)] + shlex.split(trace.context.arguments)
        trace.process = subprocess.Popen(
            args,
            cwd=str(trace.cwd),
            stdout=trace.stdout_path.open('w'),
            stderr=trace.stderr_path.open('w'),
            stdin=subprocess.DEVNULL,
        )
        trace.process.wait()
        logger.debug('process exited with code %d', trace.process.returncode)

        # Run teardown hooks
        for hook in hooks:
            hook.teardown(trace)

    def compare_trace(
        self, project: Project, original: Trace, debloated: Trace
    ) -> list[ComparisonResult]:
        """
        Compare a debloated trace against the original and return a comparison result for each
        comparator. This method will always return all failures and optionally return the successes
        if ``report_successes`` is enabled.

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

            if not result or self.report_successes:
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
            contexts.append(TraceContext(template, args, values, id=f'{id:03}'))

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
        self._values = []
        self.exhausted = False

    def __next__(self) -> Any:
        try:
            value = next(self._iter)
        except StopIteration:
            # Iterator has been exhausted, we now produce values from the cache
            self.exhausted = True
            self._iter = cycle(self._values)
            value = next(self._iter)
        else:
            # Cache the value
            self._values.append(value)
        return value
