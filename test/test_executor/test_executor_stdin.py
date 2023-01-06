from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

from differ import executor


class TestExecutorTraceStdin:
    def test_create_stdin_file_relative_path(self):
        trace = MagicMock()
        trace.context.template.stdin = Path('./filename.txt')
        trace.cwd = Path('/path/to/trace')

        app = executor.Executor(Path('/'))
        assert app.create_stdin_file(trace) == (trace.cwd / 'filename.txt')

    def test_create_stdin_file_absolute_path(self):
        trace = MagicMock()
        trace.context.template.stdin = Path('/path/to/filename.txt')
        trace.cwd = Path('/path/to/trace')

        app = executor.Executor(Path('/'))
        assert app.create_stdin_file(trace) is trace.context.template.stdin

    @patch.object(executor, 'open', new_callable=mock_open)
    def test_create_stdin_file_str(self, mock_file):
        trace = MagicMock()
        trace.context.template.stdin = 'hello world'
        trace.cwd = Path('/path/to/trace')
        trace.context.values = {'x': 1}
        template = trace.context.template.stdin_template

        app = executor.Executor(Path('/'))
        assert app.create_stdin_file(trace) is trace.default_stdin_path

        mock_file.assert_called_once_with(trace.default_stdin_path, 'wb')
        mock_file().write.assert_called_once_with(template.render.return_value.encode.return_value)
        template.render.assert_called_once_with(trace=trace, **trace.context.values)

    @patch.object(executor, 'open', new_callable=mock_open)
    def test_create_stdin_file_empty_str(self, mock_file):
        trace = MagicMock()
        trace.context.template.stdin = ''
        trace.cwd = Path('/path/to/trace')
        trace.context.values = {'x': 1}
        trace.context.template.stdin_template = None

        app = executor.Executor(Path('/'))
        assert app.create_stdin_file(trace) is trace.default_stdin_path

        mock_file.assert_called_once_with(trace.default_stdin_path, 'wb')
        mock_file().write.assert_not_called()
