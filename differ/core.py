from dataclasses import dataclass, field
from enum import Enum
from itertools import chain
from pathlib import Path
from typing import Any, Iterable, Union

import yaml


class TraceHook:
    """
    A hook that is called prior to running a trace and after the trace has executed.
    """

    def setup(self, trace: 'Trace') -> None:
        """
        Run any setup actions prior to executing a trace.
        """
        pass

    def teardown(self, trace: 'Trace') -> None:
        """
        Run any teardown actions after a trace has completed.
        """
        pass


@dataclass
class Project:
    """
    A fuzzing project containing the original binary and multiple recovered versions.
    """

    #: Original binary file path
    original: Path
    #: List of recovered binary file paths to compare against the original
    recovered: list[Path]
    #: List of the traces to run
    traces: list['TraceTemplate']

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
        recovered = [Path(item) for item in body['recovered']]
        traces = [TraceTemplate.load_dict(item) for item in body['traces']]
        return cls(original=original, recovered=recovered, traces=traces)


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
class Trace:
    """
    A concrete run of a trace template.
    """

    #: The original binary's output
    original: 'TraceProcess'
    #: The recovered binary's output
    recovered: 'TraceProcess'
    #: The trace template
    template: TraceTemplate
    #: The command line arguments used in the trace
    command_line: list[str]
    #: The fuzzing variable values
    values: dict[str, Any] = field(default_factory=dict)
    #: The list of comparison results
    results: list['ComparisonResult'] = field(default_factory=list)

    @property
    def hooks(self) -> Iterable[TraceHook]:
        """
        :returns: the list of hooks to call
        """
        for item in chain(self.template.variables.values(), self.template.comparators):
            yield item

    def run_setup_hooks(self) -> None:
        """
        Run all setup hooks.
        """
        for hook in self.hooks:
            hook.setup(self)

    def run_teardown_hooks(self) -> None:
        """
        Run all teardown hooks.
        """
        for hook in self.hooks:
            hook.teardown(self)


@dataclass
class TraceProcess:
    """
    A completed trace process of either the original binary or a recovered binary.
    """

    #: Binary file path
    binary: Path
    #: Current working directory
    cwd: str
    #: Standard output content (bytes)
    stdout: bytes = b''
    #: Standard error content (bytes)
    stderr: bytes = b''
    #: The process exist code
    exit_code: int = 0


class ComparisonStatus(Enum):
    expected = 'match'
    unexpected = 'unexpected'


@dataclass
class ComparisonResult:
    comparator: 'Comparator'
    status: ComparisonStatus
    details: str

    @classmethod
    def matches(cls, comparator: 'Comparator', details: str = ''):
        return cls(comparator, ComparisonStatus.expected, details)

    @classmethod
    def error(cls, comparator: 'Comparator', details: str = ''):
        return cls(comparator, ComparisonStatus.unexpected, details)

    def __bool__(self) -> bool:
        return self.status is ComparisonStatus.expected


class FuzzVariable(TraceHook):
    id: str = ''

    def __init__(self, name: str, config: dict):
        self.name = name
        self.values: list[Any] = config.get('values', [])

    def generate_values(self, trace: Trace) -> Iterable[Any]:
        return self.values


class Comparator(TraceHook):
    id: str = ''

    def __init__(self, config: dict):
        pass

    def compare(self, trace: Trace) -> ComparisonResult:
        raise NotImplementedError()


VARIABLE_TYPE_REGISTRY: dict[str, type[FuzzVariable]] = {}
COMPARATOR_TYPE_REGISTRY: dict[str, type[Comparator]] = {}
