from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

from differ import executor


class TestExecutorInputFiles:
    @patch.object(executor.os, 'chmod')
    def test_set_input_file_permission_copy(self, mock_chmod):
        dest = object()
        ifile = MagicMock(permission='')
        stat = ifile.source.stat.return_value
        stat.st_mode = 0o2755
        app = executor.Executor(Path('/'))
        app.set_input_file_permission(ifile, dest)
        mock_chmod.assert_called_once_with(dest, 0o755)
        ifile.source.stat.assert_called_once()

    @patch.object(executor.os, 'chmod')
    def test_set_input_file_permission_explicit(self, mock_chmod):
        dest = object()
        ifile = MagicMock(permission='755')
        app = executor.Executor(Path('/'))
        app.set_input_file_permission(ifile, dest)
        mock_chmod.assert_called_once_with(dest, 0o755)

    @patch.object(executor, 'open', new_callable=mock_open)
    def test_generate_input_file(self, mock_file):
        ifile = MagicMock()
        trace = MagicMock()
        trace.context.values = {'x': 1}
        dest = ifile.get_destination.return_value = Path('/asdf')
        content = ifile.template.render.return_value
        app = executor.Executor(Path('/'))
        app.set_input_file_permission = MagicMock()
        app.generate_input_file(trace, ifile)

        ifile.get_destination.assert_called_once_with(trace.cwd)
        ifile.template.render.assert_called_once_with(**trace.context.values)
        mock_file.assert_called_once_with(dest, 'w')
        mock_file().write.assert_called_once_with(content)
        app.set_input_file_permission.assert_called_once_with(ifile, dest)

    @patch.object(executor.shutil, 'copy')
    def test_copy_input_files(self, mock_copy):
        trace = MagicMock()
        input_files = trace.context.template.input_files = [
            MagicMock(static=True),
            MagicMock(static=False),
        ]
        static_dest = input_files[0].get_destination.return_value
        app = executor.Executor(Path('/'))
        app.set_input_file_permission = MagicMock()
        app.generate_input_file = MagicMock()

        app.copy_input_files(trace)

        input_files[0].get_destination.assert_called_once_with(trace.cwd)
        mock_copy.assert_called_once_with(str(input_files[0].source), str(static_dest))
        app.set_input_file_permission.assert_called_once_with(input_files[0], static_dest)

        app.generate_input_file.assert_called_once_with(trace, input_files[1])
