from pathlib import Path
from unittest.mock import MagicMock

from differ import executor
from differ.core import ComparisonStatus


class MockComparisonResultError(MagicMock):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.__bool__ = MagicMock(return_value=False)
        self.details = 'base'


class TestExecutorResults:
    def test_get_errors_expect_success(self):
        trace = MagicMock()
        trace.context.template.expect_success = True
        results = [MockComparisonResultError(), MagicMock()]
        app = executor.Executor(Path('/'))

        assert app.get_errors(trace, results, None) == [results[0]]

    def test_get_errors_failure_is_success(self):
        trace = MagicMock()
        trace.context.template.expect_success = False
        error = MockComparisonResultError()
        results = [MagicMock(), error]

        app = executor.Executor(Path('/'))

        assert app.get_errors(trace, results, None) == []
        assert error.status is ComparisonStatus.success
        assert error.details.startswith('base ')

    def test_get_errors_expect_failure_no_errors(self):
        trace = MagicMock()
        trace.context.template.expect_success = False
        results = []

        app = executor.Executor(Path('/'))
        errors = app.get_errors(trace, results, None)
        assert len(errors) == 1
        assert errors[0].comparator == executor.EXECUTOR_COMPARATOR.id
        assert errors[0].trace_directory is trace.cwd
        assert errors == results
