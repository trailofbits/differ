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
        ext.check_file_type = MagicMock(return_value=None)
        result = ext.compare(original, debloated)
        assert result.status is ComparisonStatus.success
        assert result.comparator == ext.id
        ext.check_file_type.assert_called_once_with(debloated, debloated.cwd / 'filename')

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
        ext.check_file_type = MagicMock(return_value=None)
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
        ext.check_file_type = MagicMock(return_value=None)
        result = ext.compare(original, debloated)
        assert result.status is ComparisonStatus.error
        assert result.comparator == ext.id
        mock_compare.assert_called_once_with('ssdeep', 'ssdeep_2')

    def test_init_mode_int(self):
        ext = files.FileComparator({'filename': 'asdf', 'mode': 755})
        assert ext.mode == 0o755

    def test_init_mode_str(self):
        ext = files.FileComparator({'filename': 'asdf', 'mode': '755'})
        assert ext.mode == 0o755

    def test_init_mode_ref(self):
        ext = files.FileComparator({'filename': 'asdf', 'mode': {'variable': 'x'}})
        assert isinstance(ext.mode, files.OctalRef)
        assert ext.mode.variable == 'x'

    def test_init_mode_default(self):
        ext = files.FileComparator({'filename': 'asdf'})
        assert ext.mode is files.MODE_NO_CHECK

    def test_init_directory(self):
        ext = files.FileComparator({'filename': 'asdf', 'type': 'directory'})
        assert ext.similarity == 0
        assert ext.path_type is files.PathType.directory

    def test_verify_original_no_similarity(self):
        trace = MagicMock(cwd=Path('/'), cache={})
        ext = files.FileComparator({'filename': 'asdf', 'type': 'directory'})
        ext.check_file_type = MagicMock(return_value=None)
        ext.verify_original(trace)
        assert trace.cache == {}

    def test_check_file_type_not_a_file(self):
        trace = MagicMock()
        filename = MagicMock()
        filename.exists.return_value = True
        filename.is_file.return_value = False
        ext = files.FileComparator({'filename': 'asdf', 'exists': True})
        assert ext.check_file_type(trace, filename)

    def test_check_file_type_not_a_directory(self):
        trace = MagicMock()
        filename = MagicMock()
        filename.exists.return_value = True
        filename.is_file.return_value = True
        filename.is_dir.return_value = False
        ext = files.FileComparator({'filename': 'asdf', 'exists': True, 'type': 'directory'})
        assert ext.check_file_type(trace, filename)

    def test_check_file_type_must_not_exist(self):
        trace = MagicMock()
        filename = MagicMock()
        filename.exists.return_value = True
        ext = files.FileComparator({'filename': 'asdf', 'exists': False})
        assert ext.check_file_type(trace, filename)

    def test_check_file_type_mode_deref(self):
        trace = MagicMock()
        trace.context.values = {'x': '755'}
        filename = MagicMock()
        filename.exists.return_value = True
        filename.is_file.return_value = True
        filename.stat.return_value.st_mode = 0o744
        ext = files.FileComparator({'filename': 'asdf', 'exists': True, 'mode': {'variable': 'x'}})
        assert ext.check_file_type(trace, filename)

    def test_compare_check_file_failed(self):
        original = MagicMock()
        debloated = MagicMock(cwd=Path('/'))

        ext = files.FileComparator({'filename': 'asdf'})
        ext.check_file_type = MagicMock(return_value='error')

        assert ext.compare(original, debloated) == ComparisonResult.error(ext, debloated, 'error')

    def test_compare_check_no_similarity(self):
        original = MagicMock()
        debloated = MagicMock(cwd=Path('/'))

        ext = files.FileComparator({'filename': 'asdf', 'similarity': 0})
        ext.check_file_type = MagicMock(return_value=None)
        ext.hash_file = MagicMock()

        assert ext.compare(original, debloated) == ComparisonResult.success(ext, debloated)
        ext.hash_file.assert_not_called()




class TestOctalRef:

    def test_get(self):
        ref = files.OctalRef.parse({'variable': 'x'})
        assert files.OctalRef.deref(ref, {'x': 755}) == 0o755
        assert files.OctalRef.deref(ref, {'x': '755'}) == 0o755
