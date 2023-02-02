from pathlib import Path
from unittest.mock import patch, MagicMock

from differ import core


class TestInputFile:
    def test_get_destination_default(self):
        ifile = core.InputFile(Path('/path/to/input_file'))
        assert ifile.get_destination(Path('/root')) == Path('/root/input_file')

    def test_get_destination_relative(self):
        ifile = core.InputFile(Path('/path/to/input_file'), Path('../blah.txt'))
        assert ifile.get_destination(Path('/root')) == Path('/blah.txt')

    def test_get_destination_abs(self):
        ifile = core.InputFile(Path('/path/to/input_file'), Path('/etc/config'))
        assert ifile.get_destination(Path('/root')) == Path('/etc/config')

    def test_get_destination_directory(self):
        ifile = core.InputFile(Path('/path/to/input_file'), Path('/etc'))
        assert ifile.get_destination(Path('/root')) == Path('/etc/input_file')

    @patch.object(core, 'JINJA_ENVIRONMENT')
    def test_template(self, mock_env):
        src = MagicMock()
        ifile = core.InputFile(src, Path('/etc'))
        assert ifile.template is mock_env.from_string.return_value
        mock_env.from_string.assert_called_once_with(src.read_text.return_value)
        src.read_text.assert_called_once_with()

    def test_load_dict(self):
        ifile = core.InputFile.load_dict({'source': '/path/to/file', 'mode': 777})
        assert ifile == core.InputFile(Path('/path/to/file'), mode='777')
