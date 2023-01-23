from unittest.mock import MagicMock, patch

from differ.comparators import primitives
from differ.core import ComparisonResult, ComparisonStatus, CrashResult, Trace


class HookComparator(primitives.HookScriptComparator):
    def __init__(self, config: dict = None):
        super().__init__('test', config or {})
        self.get_output = MagicMock(side_effect=self._get_output)

    def _get_output(self, trace: Trace):
        return trace.setup_script, trace.setup_script_output_path


class TestHookScriptComparator:
    def test_compare_ok(self):
        original = MagicMock()
        original.setup_script.returncode = 0
        original.setup_script_output_path.read_bytes.return_value = b'hello'

        debloated = MagicMock()
        debloated.setup_script.returncode = 0
        debloated.setup_script_output_path.read_bytes.return_value = b'hello'

        ext = HookComparator()
        assert ext.compare(original, debloated) == ComparisonResult.success(ext, debloated)
        original.setup_script_output_path.read_bytes.assert_called_once()
        debloated.setup_script_output_path.read_bytes.assert_called_once()

    def test_compare_skip(self):
        original = MagicMock(setup_script=None)
        debloated = MagicMock(setup_script=None)
        ext = HookComparator()
        assert ext.compare(original, debloated) == ComparisonResult.success(ext, debloated)
        original.setup_script_output_path.read_bytes.assert_not_called()
        debloated.setup_script_output_path.read_bytes.assert_not_called()

    def test_compare_returncode(self):
        original = MagicMock()
        original.setup_script.returncode = 0
        original.setup_script_output_path.read_bytes.return_value = b'hello'

        debloated = MagicMock()
        debloated.setup_script.returncode = 1
        debloated.setup_script_output_path.read_bytes.return_value = b'hello'

        ext = HookComparator()
        result = ext.compare(original, debloated)
        assert result == ComparisonResult.error(
            'test_script[exit_code]', debloated, result.details
        )

    def test_compare_output(self):
        original = MagicMock()
        original.setup_script.returncode = 0
        original.setup_script_output_path.read_bytes.return_value = b'hello'

        debloated = MagicMock()
        debloated.setup_script.returncode = 0
        debloated.setup_script_output_path.read_bytes.return_value = b'goodbye'

        ext = HookComparator()
        result = ext.compare(original, debloated)
        assert result == ComparisonResult.error('test_script[output]', debloated, result.details)

    def test_compare_skip_exit_code(self):
        original = MagicMock()
        original.setup_script.returncode = 0
        original.setup_script_output_path.read_bytes.return_value = b'hello'
        debloated = MagicMock()
        debloated.setup_script.returncode = 1
        debloated.setup_script_output_path.read_bytes.return_value = b'hello'

        ext = HookComparator({'exit_code': False})
        assert ext.compare(original, debloated).status is ComparisonStatus.success

    def test_compare_exit_code_config(self):
        original = MagicMock()
        original.setup_script.returncode = 0
        original.setup_script_output_path.read_bytes.return_value = b'hello'

        debloated = MagicMock()
        debloated.setup_script.returncode = 1
        debloated.setup_script_output_path.read_bytes.return_value = b'hello'

        ext = HookComparator({'exit_code': {'expect': 0}})
        result = ext.compare(original, debloated)
        assert result == ComparisonResult.error(
            'test_script[exit_code]', debloated, result.details
        )

    def test_compare_skip_output(self):
        original = MagicMock()
        original.setup_script.returncode = 0
        original.setup_script_output_path.read_bytes.return_value = b'hello'

        debloated = MagicMock()
        debloated.setup_script.returncode = 0
        debloated.setup_script_output_path.read_bytes.return_value = b'goodbye'

        ext = HookComparator({'output': False})
        result = ext.compare(original, debloated)
        assert result == ComparisonResult.success('test_script', debloated)

    def test_verify_original_skip(self):
        ext = HookComparator()
        assert ext.verify_original(MagicMock()) is None

    def test_verify_original_error(self):
        trace = MagicMock()
        trace.setup_script.returncode = 1
        ext = HookComparator({'exit_code': {'expect': 0}})
        result = ext.verify_original(trace)
        assert result == CrashResult(trace, result.details, 'test_script[exit_code]')

    def test_verify_original_ok(self):
        trace = MagicMock()
        trace.setup_script.returncode = 0
        ext = HookComparator({'exit_code': {'expect': 0}})
        result = ext.verify_original(trace)
        assert result is None

    def test_verify_original_skip_exit_code(self):
        ext = HookComparator({'exit_code': False})
        assert ext.verify_original(MagicMock()) is None


class TestSetupScriptComparator:
    def test_get_output(self):
        trace = MagicMock()
        ext = primitives.SetupScriptComparator({})
        assert ext.id == 'setup_script'
        assert ext.get_output(trace) == (trace.setup_script, trace.setup_script_output_path)


class TestTeardownScriptComparator:
    def test_get_output(self):
        trace = MagicMock()
        ext = primitives.TeardownScriptComparator({})
        assert ext.id == 'teardown_script'
        assert ext.get_output(trace) == (trace.teardown_script, trace.teardown_script_output_path)


class TestConcurrentScriptComparator:
    @patch.object(primitives, 'CompletedProcess')
    def test_get_output(self, mock_proc):
        trace = MagicMock()
        ext = primitives.ConcurrentScriptComparator({})
        assert ext.id == 'concurrent_script'
        assert ext.get_output(trace) == (
            mock_proc.return_value,
            trace.concurrent_script_output_path,
        )
        mock_proc.assert_called_once_with(
            trace.concurrent_script.args, trace.concurrent_script.returncode
        )

    def test_get_output_none(self):
        trace = MagicMock(concurrent_script=None)
        ext = primitives.ConcurrentScriptComparator({})
        assert ext.get_output(trace) == (None, trace.concurrent_script_output_path)
