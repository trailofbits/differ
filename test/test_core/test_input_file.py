from pathlib import Path

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
