from unittest.mock import MagicMock, patch

from differ.variables.primitives import IntVariable


class TestIntVariable:
    def test_generate_values_list(self):
        var = IntVariable('int', {'values': [1, 2, 3]})
        assert list(var.generate_values(MagicMock())) == [1, 2, 3]

    @patch('random.sample', return_value=[4, 5, 6, 7, 8])
    def test_generate_values_range(self, mock_sample):
        var = IntVariable('int', {'range': {'minimum': 1, 'maximum': 10, 'count': 5}})
        assert list(var.generate_values(MagicMock())) == [4, 5, 6, 7, 8]
        mock_sample.assert_called_once_with(range(1, 11), k=5)

    @patch('random.sample', return_value=[4, 5, 6, 7, 8])
    def test_generate_values_both(self, mock_sample):
        var = IntVariable(
            'int', {'values': [1, 2, 3], 'range': {'minimum': 1, 'maximum': 10, 'count': 5}}
        )
        assert list(var.generate_values(MagicMock())) == [1, 2, 3, 4, 5, 6, 7, 8]
        mock_sample.assert_called_once_with(range(1, 11), k=5)
