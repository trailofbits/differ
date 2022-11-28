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
    def load_dict(cls, name: str, body: Union[str, dict]):
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
    #: Original binary file path
    original: Path
    #: List of debloated binaries
    debloaters: dict[str, DebloatedBinary] = field(default_factory=dict)
    #: List of the traces to run
    templates: list['TraceTemplate'] = field(default_factory=list)

    @classmethod
    def load(cls, filename: Union[str, Path]) -> 'Project':
        """
        Load the project from a YAML file.
        """
        with open(filename, 'r') as file:
            body = yaml.safe_load(file)
        return cls.load_dict(body)

    @classmethod
    def load_dict(cls, body: dict) -> 'Project':
        original = Path(body['original'])
        templates = [TraceTemplate.load_dict(item) for item in body['templates']]
        debloaters = {
            name: DebloatedBinary.load_dict(name, value)
            for name, value in body['debloaters'].items()
        }
        return cls(
            name=body['name'],
            original=original,
            debloaters=debloaters,
            templates=templates,
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

    def __post_init__(self):
        self._arguments_template = None

    @property
    def arguments_template(self) -> jinja2.Template:
        if not self._arguments_template:
            self._arguments_template = jinja2.Template(self.arguments)
        return self._arguments_template

    @property
    def hooks(self) -> Iterator[TraceHook]:
        yield from chain(self.variables.values(), self.comparators)

    @classmethod
    def load_dict(cls, body: dict) -> 'TraceTemplate':
        arguments: str = body.get('arguments', '')
        variables_config = body.get('variable', {})
        comparators_config = body.get('comparator', [])

        variables: dict[str, FuzzVariable] = {}
        for name, config in variables_config.items():
            if isinstance(config, dict):
                id = config.pop('id')
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
    Concrete parameters of a trace template.
    """

    template: TraceTemplate
    arguments: str = ''
    values: dict[str, Any] = field(default_factory=dict)
    id: str = ''

    def __post_init__(self):
        if not self.id:
            self.id = str(uuid4())


@dataclass
class Trace:
    """
    A run of a binary with concrete parameters.
    """

    #: Path to the binary
    binary: Path
    #: Trace context, containing the concrete parameters.
    context: TraceContext
    #: The working directory where the sample is run
    cwd: Path
    #: The subprocess
    process: Optional[subprocess.Popen] = None
    #: Cache that is cleaned up when the trace is no longer needed. Comparators can use the cache
    #: to store the results of an expensive task.
    cache: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.id:
            self.id = str(uuid4())

    def setup(self) -> None:
        """
        Run all setup hooks.
        """
        for hook in self.context.template.hooks:
            hook.setup(self)

    def teardown(self) -> None:
        """
        Run all teardown hooks.
        """
        for hook in self.context.template.hooks:
            hook.teardown(self)

    def read_stdout(self, cache: bool = True) -> bytes:
        if cache:
            stdout = self.cache.get('stdout')
            if stdout is not None:
                return stdout

        stdout = self.stdout_path.read_bytes()
        if cache:
            self.cache['stdout'] = stdout
        return stdout

    def read_stderr(self, cache: bool = True) -> bytes:
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
        return self.cwd / '__differ.stdout'

    @property
    def stderr_path(self) -> Path:
        """
        :returns: the path to the process's standard error
        """
        return self.cwd / '__differ.stderr'


@dataclass
class TraceGroup:
    original: Trace
    recovered: list[Trace] = field(default_factory=list)
    comparisons: list['ComparisonResult'] = field(default_factory=list)


class ComparisonStatus(Enum):
    success = 'success'
    error = 'error'


@dataclass
class ComparisonResult:
    trace: Trace
    comparator: 'Comparator'
    status: ComparisonStatus
    details: str

    @classmethod
    def success(cls, trace: Trace, comparator: 'Comparator', details: str = ''):
        return cls(trace, comparator, ComparisonStatus.success, details)

    @classmethod
    def error(cls, trace: Trace, comparator: 'Comparator', details: str = ''):
        return cls(trace, comparator, ComparisonStatus.error, details)

    def __bool__(self) -> bool:
        return self.status is ComparisonStatus.success


class FuzzVariable(TraceHook):
    id: str = ''

    def __init__(self, name: str, config: dict):
        self.name = name

    def generate_values(self, template: TraceTemplate) -> Iterator:
        raise NotImplementedError()


class Comparator(TraceHook):
    id: str = ''

    def __init__(self, config: dict):
        pass

    def compare(self, original: Trace, recovered: Trace) -> ComparisonResult:
        raise NotImplementedError()


VARIABLE_TYPE_REGISTRY: dict[str, type[FuzzVariable]] = {}
COMPARATOR_TYPE_REGISTRY: dict[str, type[Comparator]] = {}
