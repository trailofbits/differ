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
