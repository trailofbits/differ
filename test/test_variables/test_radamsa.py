import subprocess
from unittest.mock import MagicMock, call, patch

import pytest

from differ.variables.radamsa import RadamsaConfig, RadamsaVariable

CONFIG = {'seed': ['1', '2'], 'count': 2}


class TestRadamsaConfig:
    def test_parse(self):
        assert RadamsaConfig.parse({'seed': ['1', 2], 'count': 10}) == RadamsaConfig(
            ['1', '2'], 10
        )

    def test_parse_single_seed(self):
        assert RadamsaConfig.parse({'seed': 'foo'}) == RadamsaConfig(['foo'], 5)


class TestRadamsaVariable:
    @patch('differ.variables.radamsa.RADAMSA_BIN_FILENAME')
    def test_init_error(self, mock_bin):
        mock_bin.is_file.return_value = False
        with pytest.raises(OSError):
            RadamsaVariable('var', CONFIG)

    @patch('differ.variables.radamsa.RADAMSA_BIN_FILENAME')
    @patch('subprocess.Popen')
    def test_generate_from_seed(self, mock_popen_cls, mock_bin):
        mock_bin.is_file.return_value = True
        mock_popen = mock_popen_cls.return_value
        mock_popen.communicate.return_value = b'hello\nworld\nworld\n\nasdf', b''
        ext = RadamsaVariable('var', CONFIG)
        assert sorted(ext._generate_from_seed('foo', 10)) == ['asdf', 'hello', 'world']
        mock_popen_cls.assert_called_once_with(
            [str(mock_bin), '--count', '10'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        mock_popen.communicate.assert_called_once_with(b'foo\n')

    @patch('differ.variables.radamsa.RADAMSA_BIN_FILENAME')
    def test_generate_values(self, mock_bin):
        mock_bin.is_file.return_value = True
        template = MagicMock()
        ext = RadamsaVariable('var', CONFIG)
        ext._generate_from_seed = MagicMock(side_effect=[['1', '2'], ['3', '4']])
        assert list(ext.generate_values(template)) == ['1', '2', '3', '4']
        assert ext._generate_from_seed.call_args_list == [call('1', 2), call('2', 2)]
