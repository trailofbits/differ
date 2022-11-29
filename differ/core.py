import shlex
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from itertools import chain
from pathlib import Path
from typing import Any, Iterator, Optional, Union
from uuid import uuid4

import jinja2
import yaml


class TraceHook:
    """
    A hook that is called prior to running a trace and after the trace has executed.
    """

    def setup(self, trace: 'Trace') -> None:
        """
        Run any setup actions prior to executing a trace.
        """

    def teardown(self, trace: 'Trace') -> None:
        """
        Run any teardown actions after a trace has completed.
        """


@dataclass
class DebloatedBinary:
    """
    A debloated binary to evaluate.
    """

    #: Debloater engine name
    engine: str
    #: Debloated binary
    binary: Path

    @classmethod
    def load_dict(cls, name: str, body: Union[str, dict]) -> 'DebloatedBinary':
        """
        Load the delobated binary from a dictionary.

        :param name: the debloater engine name
        :param body: debloated binary dictionary
        """
        if isinstance(body, str):
            return cls(name, Path(body))
        return cls(name, Path(body['binary']))


@dataclass
class Project:
    """
    A fuzzing project containing the original binary and multiple recovered versions.
    """

    #: Unique project name
    name: str
    #: Project directory
    directory: Path
    #: Original binary file path
    original: Path
    #: List of debloated binaries
    debloaters: dict[str, DebloatedBinary] = field(default_factory=dict)
    #: List of the traces to run
    templates: list['TraceTemplate'] = field(default_factory=list)

    def context_directory(self, context: 'TraceContext') -> Path:
        """
        :returns: the trace context working directory
        """
        return self.directory / f'trace-{context.id}'

    def trace_directory(self, context: 'TraceContext', debloater_engine: str) -> Path:
        """
        :returns: the trace working directory within a context
        """
        return self.context_directory(context) / debloater_engine

    def crash_filename(self, context: 'TraceContext') -> Path:
        """
        :returns: the crash report filename when the original binary does not behave correctly
        """
        return self.directory / f'crash-{context.id}.yml'

    def report_filename(self, trace: 'Trace', successful: bool) -> Path:
        """
        :returns: the report filename for a trace
        """
        engine = trace.debloater_engine
        if successful:
            engine += '-success'
        else:
            engine += '-error'

        return self.directory / f'report-{engine}-{trace.context.id}.yml'

    def save_report(self, trace: 'Trace', results: list['ComparisonResult']) -> None:
        """
        Save the list of comparison results to a YAML report.

        :param trace: trace that was executed
        :param results: trace comparison results
        """
        docs = []
        args = trace.process.args if trace.process else shlex.split(trace.context.arguments)
        body = {
            'values': trace.context.values,
            'trace_directory': str(trace.cwd),
            'results': docs,
            'arguments': args,
        }
        for result in results:
            doc = {
                'comparator': result.comparator,
                'details': result.details,
                'status': result.status.value,
            }
            docs.append(doc)

        successful = all(result for result in results)
        with open(self.report_filename(trace, successful), 'w') as file:
            file.write(yaml.safe_dump(body))

    @classmethod
    def load(cls, root: Path, filename: Union[str, Path]) -> 'Project':
        """
        Load the project from a YAML file.

        :param root: root directory for storing all project data
        :param body: project YAML file
        :returns: the parsed project object
        """
        with open(filename, 'r') as file:
            body = yaml.safe_load(file)
        return cls.load_dict(root, body)

    @classmethod
    def load_dict(cls, root: Path, body: dict) -> 'Project':
        """
        Load a project from a dictionary.

        :param root: root directory for storing all project data
        :param body: project dictionary
        :returns: the parsed project object
        """
        original = Path(body['original'])
        templates = [TraceTemplate.load_dict(item) for item in body['templates']]
        debloaters = {
            name: DebloatedBinary.load_dict(name, value)
            for name, value in body['debloaters'].items()
        }

        if not original.is_absolute():
            # Resolve the original binary to an absolute file path, relative to the directory where
            # the project file is located.
            original = (root.parent / original).absolute()

        for debloater in debloaters.values():
            if not debloater.binary.is_absolute():
                # Resolve the debloated binary to an absolute file path, relative to the directory
                # where the project file is located.
                debloater.binary = (root.parent / debloater.binary).absolute()

        return cls(
            name=body['name'],
            original=original,
            debloaters=debloaters,
            templates=templates,
            directory=root / body['name'],
        )


@dataclass
class TraceTemplate:
    """
    A trace configuration template.
    """

    #: Command line arguments
    arguments: str = ''
    #: Fuzzing input variables
    variables: dict[str, 'FuzzVariable'] = field(default_factory=dict)
    #: List of comparators to validate the original against each recovered binary
    comparators: list['Comparator'] = field(default_factory=list)
    #: Expect a successful run on both the original and the recovered binary. If this is ``False``,
    #: then the recovered binary is expected to fail.
    expect_success: bool = True
    #: Autogenerated id
    id: str = ''

    def __post_init__(self):
        self._arguments_template = None
        self.id = str(uuid4())

    @property
    def arguments_template(self) -> jinja2.Template:
        """
        :returns: the Jinja2 template object for the command line arguments
        """
        if not self._arguments_template:
            self._arguments_template = jinja2.Template(self.arguments)
        return self._arguments_template

    @property
    def hooks(self) -> Iterator[TraceHook]:
        """
        :returns: a generator that yields the hooks the need to execute prior to after a trace.
        """
        yield from chain(self.variables.values(), self.comparators)

    @classmethod
    def load_dict(cls, body: dict) -> 'TraceTemplate':
        """
        Load the trace template from a dictionary.
        """
        arguments: str = body.get('arguments', '')
        variables_config = body.get('variables', {})
        comparators_config = body.get('comparators', [])

        variables: dict[str, FuzzVariable] = {}
        for name, config in variables_config.items():
            if isinstance(config, dict):
                id = config.pop('type')
            else:
                id = str(config)
                config = {}

            variable_cls = VARIABLE_TYPE_REGISTRY[id]
            variables[name] = variable_cls(name, config)

        comparators: list[Comparator] = []
        for config in comparators_config:
            if isinstance(config, dict):
                id = config.pop('id')
            else:
                id = str(config)
                config = {}

            comparator_cls = COMPARATOR_TYPE_REGISTRY[id]
            comparators.append(comparator_cls(config))

        return cls(
            arguments=arguments,
            variables=variables,
            comparators=comparators,
        )


@dataclass
class TraceContext:
    """
    Concrete parameters of a trace template. Each :class:`TraceTemplate` will create multiple trace
    context objects, where each context contains concrete values for each variable in a unique
    permentation.
    """

    #: Origin trace template
    template: TraceTemplate
    #: Populate command line arguments based on variable values
    arguments: str = ''
    #: Concrete variable values
    values: dict[str, Any] = field(default_factory=dict)
    #: Unique context id which is auto generated if not specified
    id: str = ''

    def __post_init__(self):
        if not self.id:
            self.id = str(uuid4())


@dataclass
class Trace:
    """
    A execution of a binary within a trace context. Each :class:`TraceContext` is executed once for
    each deblaoted binary and once for the original binary.
    """

    #: Path to the binary
    binary: Path
    #: Trace context, containing the concrete parameters.
    context: TraceContext
    #: The working directory where the sample is run
    cwd: Path
    #: The debloater engine used on the binary
    debloater_engine: str
    #: The subprocess
    process: Optional[subprocess.Popen] = None
    #: Cache that is cleaned up when the trace is no longer needed. Comparators can use the cache
    #: to store the results of an expensive task.
    cache: dict[str, Any] = field(default_factory=dict)

    def read_stdout(self, cache: bool = True) -> bytes:
        """
        Read the process's recorded standard output and optionally cache the content in memory to
        avoid duplicate read operations.

        :param cache: attempt to read the content from the cache and update the cache when finished
        :returns: the process's recorded standard output
        """
        if cache:
            stdout = self.cache.get('stdout')
            if stdout is not None:
                return stdout

        stdout = self.stdout_path.read_bytes()
        if cache:
            self.cache['stdout'] = stdout
        return stdout

    def read_stderr(self, cache: bool = True) -> bytes:
        """
        Read the process's recorded standard error and optionally cache the content in memory to
        avoid duplicate read operations.

        :param cache: attempt to read the content from the cache and update the cache when finished
        :returns: the process's recorded standard error
        """
        if cache:
            stderr = self.cache.get('stderr')
            if stderr is not None:
                return stderr

        stderr = self.stderr_path.read_bytes()
        if cache:
            self.cache['stderr'] = stderr
        return stderr

    @property
    def stdout_path(self) -> Path:
        """
        :returns: the path to the process's standard output
        """
        return self.cwd / '__differ-stdout.bin'

    @property
    def stderr_path(self) -> Path:
        """
        :returns: the path to the process's standard error
        """
        return self.cwd / '__differ-stderr.bin'


class ComparisonStatus(Enum):
    """
    A :class:`Comparator` status. This enumeration signals whether the results from the debloated
    binary match the original's.
    """

    #: The comparsion was successful (e.g.- the debloated output matches the original's)
    success = 'success'
    #: The comparsion failed (e.g.- the debloated output does not match the original's)
    error = 'error'


@dataclass
class ComparisonResult:
    """
    The result of a single comparison of a debloated binary against the original.
    """

    #: The comparison status
    status: ComparisonStatus
    #: The comparator that produced the result
    comparator: str
    #: The debloated binary working directory, containing logs and input files
    trace_directory: Path
    #: The concrete variable values used in the trace
    values: dict
    #: Additional details
    details: str = ''

    @classmethod
    def error(
        cls, comparator: 'Comparator', trace: Trace, details: str = ''
    ) -> 'ComparisonResult':
        """
        Create a failed comparison result.

        :param comparator: the comparator that produced the result
        :param trace: the debloated binary trace
        :param details: additional details
        """
        return cls(
            values=trace.context.values,
            trace_directory=trace.cwd,
            comparator=comparator.id,
            details=details,
            status=ComparisonStatus.error,
        )

    @classmethod
    def success(
        cls, comparator: 'Comparator', trace: Trace, details: str = ''
    ) -> 'ComparisonResult':
        """
        Create a successful comparison result.

        :param comparator: the comparator that produced the result
        :param trace: the debloated binary trace
        :param details: additional details
        """
        return cls(
            values=trace.context.values,
            trace_directory=trace.cwd,
            comparator=comparator.id,
            details=details,
            status=ComparisonStatus.success,
        )

    def __bool__(self) -> bool:
        """
        :returns: ``True`` if the comparison was successful, ``False`` otherwise
        """
        return self.status is ComparisonStatus.success


@dataclass
class CrashResult:
    """
    A crash or unexpected result produced by the original binary. This class is used when the
    original binary crashed or otherwise did not behave as expected based on the trace template.
    """

    #: The trace working directory for the original binary
    trace_directory: Path
    #: Concrete variable values
    values: dict
    #: Additional details
    details: str = ''

    def save(self, filename: Path) -> None:
        """
        Save the crash result to a YAML file.

        :param filename: destination filename
        """
        body = {
            'values': self.values,
            'trace_directory': self.trace_directory,
            'details': self.details,
        }
        with open(filename, 'w') as file:
            file.write(yaml.safe_dump(body))


class FuzzVariable(TraceHook):
    """
    An input variable that has multiple values generated when evaluating a debloated binary against
    the original. Subclasses must implement two methods:

    - ``__init__()`` - parse the configuration and setup how values will be generated
    - ``generate_values()`` - yield generated values based on the configuration

    A fuzz variable is also a :class:`TraceHook` subclass so subclasses can implement the
    :meth:`~TraceHook.setup` and :meth:`~TraceHook.teardown` methods to run any actions before a
    trace is run and after it has completed.

    Fuzz variables should be bounded to yield a set number of values, such as limiting the number
    of values that are generated with a ``size`` configuration parameter.
    """

    id: str = ''

    def __init__(self, name: str, config: dict):
        """
        :param name: the variable name
        :param config: the variable configuration
        """
        self.name = name

    def generate_values(self, template: TraceTemplate) -> Iterator:
        """
        Generate concrete values for the template.

        :param template: trace template:
        :returns: a generator that yields generated values
        """
        raise NotImplementedError()


class Comparator(TraceHook):
    """
    Rules and logic for comparing a debloated binary trace against the original binary trace, such
    as comparing the standard output or exit code, to verify that the debloated behavior matches
    the original.

    Subclasses must implement three methods:

    - ``__init__`` - parse the configuration and setup the comparator
    - ``verify_original`` - verify that the original trace output matches what is expected
    - ``compare`` - compare the debloated trace against the original

    Comparators can use the :data:`Trace.cache` dictionary to cache data between runs.
    """

    id: str = ''

    def __init__(self, config: dict):
        """
        :param config: comparator configuration
        """
        pass

    def verify_original(self, original: Trace) -> Optional[CrashResult]:
        """
        Verify that the original trace behaved as expected and return a crash result if the
        original deviated from the expected behavior.

        :param original: the original trace
        :returns: a crash result on error
        """
        pass

    def compare(self, original: Trace, debloated: Trace) -> ComparisonResult:
        """
        Compare a debloated binary's trace against the orginal and return a comparison result.

        :param original: the original trace
        :param debloated: the debloated trace
        :returns: the
        """
        raise NotImplementedError()


#: Registry for all available variable classes. This is populated by the
# :func:`~differ.variables.load_variables` function.
VARIABLE_TYPE_REGISTRY: dict[str, type[FuzzVariable]] = {}

#: Registry for all available comparator classes. This is populated by the
# :func:`~differ.comparators.load_comparators` function.
COMPARATOR_TYPE_REGISTRY: dict[str, type[Comparator]] = {}
