from pathlib import Path
from unittest.mock import MagicMock, call, mock_open, patch

from differ.comparators import files
from differ.core import ComparisonResult, ComparisonStatus


class TestFileComparator:
    @patch.object(files.FileComparator, 'hash_file')
    def test_verify_original(self, mock_hash_file):
        mock_hash_file.return_value = ('sha1', 'ssdeep')
        trace = MagicMock()
        trace.cwd = Path('./')
        trace.cache = {}
        filename = trace.cwd / __file__

        ext = files.FileComparator({'filename': __file__})
        assert ext.verify_original(trace) is None
        assert trace.cache == {f'{__file__}_sha1': 'sha1', f'{__file__}_ssdeep': 'ssdeep'}
        mock_hash_file.assert_called_once_with(filename)

    def test_verify_original_error(self):
        trace = MagicMock()
        trace.cwd = Path('./')
        ext = files.FileComparator({'filename': 'does/not/exist.asdf'})
        result = ext.verify_original(trace)
        assert result is not None
        assert result.trace is trace
        assert result.comparator is ext

    @patch.object(files.hashlib, 'sha1')
    @patch.object(files.ssdeep, 'Hash')
    def test_hash_file(self, mock_ssdeep_cls, mock_sha1_cls):
        ssdeep = mock_ssdeep_cls.return_value
        sha1 = mock_sha1_cls.return_value
        filename = MagicMock()
        filename.open = mock_open()
        blocks = [b'block1', b'block2', b'']
        with filename.open('rb') as file:
            file.read.side_effect = blocks

        assert files.FileComparator.hash_file(filename) == (
            sha1.hexdigest.return_value,
            ssdeep.digest.return_value,
        )
        mock_ssdeep_cls.assert_called_once()
        mock_sha1_cls.assert_called_once()
        sha1.update.call_args_list == [call(block) for block in blocks[:-1]]
        ssdeep.update.call_args_list == [call(block) for block in blocks[:-1]]
        assert file.read.call_count == 3

    @patch.object(files.ssdeep, 'compare')
    @patch.object(files.FileComparator, 'hash_file')
    def test_compare_sha1_matches(self, mock_hash_file, mock_compare):
        original = MagicMock()
        original.cache = {'filename_sha1': 'sha1', 'filename_ssdeep': 'ssdeep'}
        debloated = MagicMock()
        debloated.cwd = Path('/')
        mock_hash_file.return_value = ('sha1', 'ssdeep')

        ext = files.FileComparator({'filename': 'filename'})
        result = ext.compare(original, debloated)
        assert result.status is ComparisonStatus.success
        assert result.comparator == ext.id

    @patch.object(files.ssdeep, 'compare')
    @patch.object(files.FileComparator, 'hash_file')
    def test_compare_ssdeep_matches(self, mock_hash_file, mock_compare):
        original = MagicMock()
        original.cache = {'filename_sha1': 'sha1', 'filename_ssdeep': 'ssdeep'}
        debloated = MagicMock()
        debloated.cwd = Path('/')
        mock_hash_file.return_value = ('sha1_2', 'ssdeep_2')
        mock_compare.return_value = 95

        ext = files.FileComparator({'filename': 'filename', 'similarity': 90})
        result = ext.compare(original, debloated)
        assert result.status is ComparisonStatus.success
        assert result.comparator == ext.id
        mock_compare.assert_called_once_with('ssdeep', 'ssdeep_2')

    @patch.object(files.ssdeep, 'compare')
    @patch.object(files.FileComparator, 'hash_file')
    def test_compare_no_match(self, mock_hash_file, mock_compare):
        original = MagicMock()
        original.cache = {'filename_sha1': 'sha1', 'filename_ssdeep': 'ssdeep'}
        debloated = MagicMock()
        debloated.cwd = Path('/')
        mock_hash_file.return_value = ('sha1_2', 'ssdeep_2')
        mock_compare.return_value = 89

        ext = files.FileComparator({'filename': 'filename', 'similarity': 90})
        result = ext.compare(original, debloated)
        assert result.status is ComparisonStatus.error
        assert result.comparator == ext.id
        mock_compare.assert_called_once_with('ssdeep', 'ssdeep_2')
