import errno
import subprocess
from itertools import cycle
from pathlib import Path
from typing import Any

from .core import (
    ComparisonResult,
    FuzzVariable,
    Project,
    Trace,
    TraceContext,
    TraceTemplate,
)


class Executor:
    """
    Project executor that executes an entire project and produces a report of results.
    """

    def __init__(self, root: Path, max_permutations: int = 100):
        """
        :param root: root directory to store results
        :param max_permutations: the maximum number of parameter permutations to execute for a
            single trace
        """
        self.root = root
        self.max_permutations = max_permutations

    def trace_context_dir(self, project: Project, context: TraceContext) -> Path:
        """
        :returns: the trace context directory
        """
        return self.root / project.name / f'trace-{context.id}'

    def run_project(self, project: Project) -> None:
        """
        Run a project.

        :param project: the project
        """
        project_dir = self.root / project.name
        if project_dir.exists():
            # The project directory must not exist
            raise FileExistsError(errno.EEXIST, str(project_dir))

        project_dir.mkdir()

        for template in project.templates:
            contexts = self.generate_contexts(project, template)
            for context in contexts:
                self.run_context(project, context)

    def run_context(self, project: Project, context: TraceContext) -> None:
        context_dir = self.trace_context_dir(project, context)
        if context_dir.exists():
            raise FileExistsError(errno.EEXIST, str(context_dir))

        context_dir.mkdir()
        original_trace = self.create_trace(project, context, project.original, '__original__')
        self.run_trace(project, original_trace)

        for debloater in project.debloaters.values():
            trace = self.create_trace(project, context, debloater.binary, debloater.engine)
            self.run_trace(project, trace)
            self.compare_trace(project, original_trace, trace)

    def run_trace(self, project: Project, trace: Trace) -> None:
        hooks = list(trace.context.template.hooks)
        for hook in hooks:
            hook.setup(trace)

        trace.process = subprocess.Popen(
            f'{trace.binary} {trace.context.arguments}',
            cwd=str(trace.cwd),
            stdout=trace.stdout_path.open('w'),
            stderr=trace.stderr_path.open('w'),
            stdin=subprocess.DEVNULL,
        )
        trace.process.wait()

        for hook in hooks:
            hook.teardown(trace)

    def compare_trace(
        self, project: Project, original_trace: Trace, recovered_trace: Trace
    ) -> list[ComparisonResult]:
        comparators = original_trace.context.template.comparators
        results = []
        for comparator in comparators:
            result = comparator.compare(original_trace, recovered_trace)
            results.append(result)
        return results

    def create_trace(
        self, project: Project, context: TraceContext, binary: Path, name: str
    ) -> Trace:
        """
        Create a trace for a single binary. This creates the trace directory and links the binary
        into the trace directory.

        :param project: differ project
        :param context: trace context with generated variable values
        :param binary: binary to execute
        :param name: engine name, used as the directory name to store results
        :returns: the created trace object
        """
        cwd = self.trace_context_dir(project, context) / name
        if not cwd.exists():
            raise FileExistsError(errno.EEXIST, str(cwd))

        cwd.mkdir()
        link = cwd / binary.name
        link.symlink_to(binary)
        trace = Trace(link, context, cwd)

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
        generators: list[VariableValueGenerator] = []
        for variable in template.variables.values():
            generators.append(VariableValueGenerator(template, variable))

        names = [item.variable.name for item in generators]
        count = 0
        done = False
        values: list[dict] = []
        while not done:
            values.append({name: next(generator) for name, generator in zip(names, generators)})
            count += 1
            done = (
                all(generator.exhausted for generator in generators)
                or count >= self.max_permutations
            )

        return values


class VariableValueGenerator:
    def __init__(self, template: TraceTemplate, variable: FuzzVariable):
        self.variable = variable
        self._iter = variable.generate_values(template)
        self._values = []
        self.exhausted = False

    def __next__(self) -> Any:
        try:
            value = next(self._iter)
        except StopIteration:
            self.exhausted = True
            self._iter = cycle(self._values)
            value = next(self._iter)
        else:
            self._values.append(value)
        return value
