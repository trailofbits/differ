from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

from differ import executor


class TestExecutorInputFiles:
    @patch.object(executor.os, 'chmod')
    @patch.object(executor.os, 'utime')
    def test_set_input_file_mode_copy(self, mock_utime, mock_chmod):
        dest = object()
        ifile = MagicMock(mode='')
        stat = ifile.source.stat.return_value
        stat.st_mode = 0o2755
        app = executor.Executor(Path('/'))
        app.set_input_file_mode(ifile, dest)
        mock_chmod.assert_called_once_with(dest, 0o755)
        ifile.source.stat.assert_called_once()
        mock_utime.assert_called_once_with(dest, ns=(stat.st_atime_ns, stat.st_mtime_ns))

    @patch.object(executor.os, 'chmod')
    @patch.object(executor.os, 'utime')
    def test_set_input_file_mode_explicit(self, mock_utime, mock_chmod):
        dest = object()
        ifile = MagicMock(mode='755')
        stat = ifile.source.stat.return_value
        app = executor.Executor(Path('/'))
        app.set_input_file_mode(ifile, dest)
        mock_chmod.assert_called_once_with(dest, 0o755)
        mock_utime.assert_called_once_with(dest, ns=(stat.st_atime_ns, stat.st_mtime_ns))

    @patch.object(executor, 'open', new_callable=mock_open)
    def test_generate_input_file(self, mock_file):
        ifile = MagicMock()
        trace = MagicMock()
        trace.context.values = {'x': 1}
        dest = ifile.get_destination.return_value = Path('/asdf')
        content = ifile.template.render.return_value
        app = executor.Executor(Path('/'))
        app.set_input_file_mode = MagicMock()
        app.generate_input_file(trace, ifile)

        ifile.get_destination.assert_called_once_with(trace.cwd)
        ifile.template.render.assert_called_once_with(trace=trace, **trace.context.values)
        mock_file.assert_called_once_with(dest, 'w')
        mock_file().write.assert_called_once_with(content)
        app.set_input_file_mode.assert_called_once_with(ifile, dest)

    @patch.object(executor, 'open', new_callable=mock_open)
    def test_generate_input_file_mkdir(self, mock_file):
        ifile = MagicMock()
        trace = MagicMock()
        trace.context.values = {'x': 1}
        dest = ifile.get_destination.return_value = MagicMock()
        dest.parent.exists.return_value = False

        content = ifile.template.render.return_value
        app = executor.Executor(Path('/'))
        app.set_input_file_mode = MagicMock()
        app.generate_input_file(trace, ifile)

        ifile.get_destination.assert_called_once_with(trace.cwd)
        ifile.template.render.assert_called_once_with(trace=trace, **trace.context.values)
        mock_file.assert_called_once_with(dest, 'w')
        mock_file().write.assert_called_once_with(content)
        app.set_input_file_mode.assert_called_once_with(ifile, dest)
        dest.parent.mkdir.assert_called_once_with(parents=True)

    @patch.object(executor.shutil, 'copy')
    def test_copy_input_files(self, mock_copy):
        trace = MagicMock()
        input_files = trace.context.template.input_files = [
            MagicMock(static=True, source=MagicMock(is_dir=MagicMock(return_value=False))),
            MagicMock(static=False, source=MagicMock(is_dir=MagicMock(return_value=False))),
        ]

        static_dest = input_files[0].get_destination.return_value
        app = executor.Executor(Path('/'))
        app.set_input_file_mode = MagicMock()
        app.generate_input_file = MagicMock()

        app.copy_input_files(trace)

        input_files[0].get_destination.assert_called_once_with(trace.cwd)
        mock_copy.assert_called_once_with(str(input_files[0].source), str(static_dest))
        app.set_input_file_mode.assert_called_once_with(input_files[0], static_dest)

        app.generate_input_file.assert_called_once_with(trace, input_files[1])

    @patch.object(executor.shutil, 'copytree')
    def test_copy_input_files_static_directory(self, mock_copytree):
        input_file = MagicMock(static=True)
        input_file.source.is_dir.return_value = True
        trace = MagicMock()
        trace.context.template.input_files = [input_file]

        app = executor.Executor(Path('/'))
        app.copy_input_files(trace)

        mock_copytree.assert_called_once_with(
            input_file.source, input_file.get_destination.return_value
        )

    @patch.object(executor.shutil, 'copy')
    def test_copy_input_files_mkdir(self, mock_copy):
        input_file = MagicMock(static=True)
        input_file.source.is_dir.return_value = False
        dest = input_file.get_destination.return_value
        dest.parent.exists.return_value = False

        trace = MagicMock()
        trace.context.template.input_files = [input_file]

        ext = executor.Executor(Path('/'))
        ext.set_input_file_mode = MagicMock()

        ext.copy_input_files(trace)

        dest.parent.mkdir.assert_called_once_with(parents=True)
        mock_copy.assert_called_once_with(str(input_file.source), str(dest))
        ext.set_input_file_mode.assert_called_once_with(input_file, dest)
