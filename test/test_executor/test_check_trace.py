from pathlib import Path
from unittest.mock import MagicMock

from differ import executor


class TestExecutorCheckTrace:
    def test_check_original_trace_ok(self):
        comparator = MagicMock()
        comparator.verify_original.return_value = None

        trace = MagicMock()
        trace.context.template.comparators = [comparator]

        app = executor.Executor(Path('/'))
        app.check_trace_crash = MagicMock(return_value=None)

        assert app.check_original_trace(MagicMock(), trace) is None

        app.check_trace_crash.assert_called_once_with(trace)
        comparator.verify_original.assert_called_once_with(trace)

    def test_check_original_trace_crash(self):
        comparator = MagicMock()
        comparator.verify_original.return_value = None

        trace = MagicMock()
        trace.context.template.comparators = [comparator]

        crash = object()
        app = executor.Executor(Path('/'))
        app.check_trace_crash = MagicMock(return_value=crash)

        assert app.check_original_trace(MagicMock(), trace) is crash

        app.check_trace_crash.assert_called_once_with(trace)
        comparator.verify_original.assert_not_called()

    def test_check_original_trace_comparator_crash(self):
        comparator = MagicMock()
        crash = comparator.verify_original.return_value = object()

        trace = MagicMock()
        trace.context.template.comparators = [comparator]

        app = executor.Executor(Path('/'))
        app.check_trace_crash = MagicMock(return_value=None)

        assert app.check_original_trace(MagicMock(), trace) is crash

        app.check_trace_crash.assert_called_once_with(trace)
        comparator.verify_original.assert_called_once_with(trace)

    def test_check_trace_crash_ok(self):
        trace = MagicMock()
        trace.timed_out = False
        trace.context.template.timeout.expected = False
        trace.crash_result = None

        app = executor.Executor(Path('/'))
        assert app.check_trace_crash(trace) is None

    def test_check_trace_crash_ok_timeout(self):
        trace = MagicMock()
        trace.timed_out = True
        trace.context.template.timeout.expected = True
        trace.crash_result = None

        app = executor.Executor(Path('/'))
        assert app.check_trace_crash(trace) is None

    def test_check_trace_crash_unexpected_timeout(self):
        trace = MagicMock()
        trace.timed_out = True
        trace.context.template.timeout.expected = False
        trace.crash_result = None

        app = executor.Executor(Path('/'))
        crash = app.check_trace_crash(trace)
        assert crash
        assert crash.trace is trace

    def test_check_trace_crash_expected_timeout(self):
        trace = MagicMock()
        trace.timed_out = False
        trace.context.template.timeout.expected = True
        trace.crash_result = None

        app = executor.Executor(Path('/'))
        crash = app.check_trace_crash(trace)
        assert crash
        assert crash.trace is trace

    def test_check_trace_crash_result(self):
        trace = MagicMock()
        trace.timed_out = False
        trace.context.template.timeout.expected = False
        crash = trace.crash_result = object()

        app = executor.Executor(Path('/'))
        assert app.check_trace_crash(trace) is crash

    def test_check_trace_crash_with_timeout(self):
        trace = MagicMock()
        trace.timed_out = True
        trace.context.template.timeout.expected = True
        trace.crash_result = object()

        app = executor.Executor(Path('/'))
        assert app.check_trace_crash(trace) is None
