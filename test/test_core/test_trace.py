import signal
from pathlib import Path
from unittest.mock import MagicMock, patch

from differ import core


class TestTrace:
    @patch.object(core, 'os')
    def test_env_base(self, mock_os):
        mock_os.environ = {'x': '1'}
        trace = core.Trace(Path('/binary'), MagicMock(), Path('/'), 'debloater')
        assert trace.env() == {
            'x': '1',
            'DIFFER_TRACE_DIR': str(trace.cwd),
            'DIFFER_TRACE_DEBLOATER': trace.debloater_engine,
            'DIFFER_TRACE_BINARY': str(trace.binary),
            'DIFFER_CONTEXT_ID': trace.context.id,
        }

    @patch.object(core, 'os')
    def test_env_process(self, mock_os):
        mock_os.environ = {'x': '1'}
        trace = core.Trace(
            Path('/binary'), MagicMock(), Path('/'), 'debloater', process=MagicMock()
        )
        assert trace.env() == {
            'x': '1',
            'DIFFER_TRACE_DIR': str(trace.cwd),
            'DIFFER_TRACE_DEBLOATER': trace.debloater_engine,
            'DIFFER_TRACE_BINARY': str(trace.binary),
            'DIFFER_CONTEXT_ID': trace.context.id,
            'DIFFER_TRACE_PID': str(trace.process.pid),
            'DIFFER_TRACE_EXIT_CODE': str(trace.process.returncode),
            'DIFFER_TRACE_STDOUT': str(trace.stdout_path),
            'DIFFER_TRACE_STDERR': str(trace.stderr_path),
        }

    @patch.object(core, 'os')
    def test_env_concurrent(self, mock_os):
        mock_os.environ = {'x': '1'}
        trace = core.Trace(
            Path('/binary'), MagicMock(), Path('/'), 'debloater', concurrent_script=MagicMock()
        )
        assert trace.env() == {
            'x': '1',
            'DIFFER_TRACE_DIR': str(trace.cwd),
            'DIFFER_TRACE_DEBLOATER': trace.debloater_engine,
            'DIFFER_TRACE_BINARY': str(trace.binary),
            'DIFFER_CONTEXT_ID': trace.context.id,
            'DIFFER_CONCURRENT_PID': str(trace.concurrent_script.pid),
            'DIFFER_CONCURRENT_EXIT_CODE': str(trace.concurrent_script.returncode),
        }

    @patch.object(core, 'os')
    def test_env_no_inherit(self, mock_os):
        mock_os.environ = {'x': '1'}
        trace = core.Trace(Path('/binary'), MagicMock(), Path('/'), 'debloater')
        assert trace.env(inherit=False) == {
            'DIFFER_TRACE_DIR': str(trace.cwd),
            'DIFFER_TRACE_DEBLOATER': trace.debloater_engine,
            'DIFFER_TRACE_BINARY': str(trace.binary),
            'DIFFER_CONTEXT_ID': trace.context.id,
        }

    @patch.object(core.os, 'WIFSIGNALED', return_value=True)
    @patch.object(core.os, 'WTERMSIG', return_value=signal.SIGINT.value)
    def test_crash_result(self, mock_termsig, mock_signaled):
        context = MagicMock()
        context.template.expect_signal = 0
        trace = core.Trace(Path('/'), context, Path('/'), 'debloater')

        result = trace.crash_result
        assert trace.crashed
        assert trace.crash_signal is signal.SIGINT
        assert result.trace is trace

    @patch.object(core.os, 'WIFSIGNALED', return_value=True)
    @patch.object(core.os, 'WTERMSIG', return_value=signal.SIGINT.value)
    def test_crash_result_expected(self, mock_termsig, mock_signaled):
        context = MagicMock()
        context.template.expect_signal = signal.SIGINT.value
        trace = core.Trace(Path('/'), context, Path('/'), 'debloater')

        result = trace.crash_result
        assert trace.crashed
        assert trace.crash_signal is signal.SIGINT
        assert result is None
