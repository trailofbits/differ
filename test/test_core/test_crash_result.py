from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

from differ import core


class MockComparator(core.Comparator):
    id = 'mock_comparator'

    def __init__(self):
        super().__init__({})


class TestCrashResult:
    @patch.object(core, 'open', new_callable=mock_open)
    @patch.object(core.yaml, 'safe_dump')
    def test_save(self, mock_safe_dump, mock_file):
        trace = MagicMock()
        trace.context.arguments = 'x y'
        details = 'DETAILS'
        comparator = MockComparator()
        filename = Path('/asdf')

        result = core.CrashResult(trace, details, comparator)
        result.save(filename)

        mock_file.assert_called_once_with(filename, 'w')
        handle = mock_file()
        handle.write.assert_called_once_with(mock_safe_dump.return_value)
        mock_safe_dump.assert_called_once_with(
            {
                'values': trace.context.values,
                'trace_directory': str(trace.cwd),
                'details': details,
                'arguments': ['x', 'y'],
                'comparator': 'mock_comparator',
            }
        )

    @patch.object(core, 'open', new_callable=mock_open)
    @patch.object(core.yaml, 'safe_dump')
    def test_save_id(self, mock_safe_dump, mock_file):
        trace = MagicMock()
        trace.context.arguments = 'x y'
        details = 'DETAILS'
        filename = Path('/asdf')

        result = core.CrashResult(trace, details, 'mock_comparator_str')
        result.save(filename)

        mock_file.assert_called_once_with(filename, 'w')
        handle = mock_file()
        handle.write.assert_called_once_with(mock_safe_dump.return_value)
        mock_safe_dump.assert_called_once_with(
            {
                'values': trace.context.values,
                'trace_directory': str(trace.cwd),
                'details': details,
                'arguments': ['x', 'y'],
                'comparator': 'mock_comparator_str',
            }
        )
