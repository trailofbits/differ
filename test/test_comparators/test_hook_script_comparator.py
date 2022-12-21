from unittest.mock import MagicMock, patch

from differ.comparators import primitives
from differ.core import ComparisonResult, ComparisonStatus, Trace


class HookComparator(primitives.HookScriptComparator):
    def __init__(self):
        super().__init__('test', {})
        self.get_output = MagicMock(side_effect=self._get_output)

    def _get_output(self, trace: Trace):
        return trace.setup_script, trace.setup_script_output


class TestHookScriptComparator:
    def test_compare_ok(self):
        original = MagicMock()
        original.setup_script.returncode = 0
        original.setup_script_output.read_bytes.return_value = b'hello'

        debloated = MagicMock()
        debloated.setup_script.returncode = 0
        debloated.setup_script_output.read_bytes.return_value = b'hello'

        ext = HookComparator()
        assert ext.compare(original, debloated) == ComparisonResult.success(ext, debloated)
        original.setup_script_output.read_bytes.assert_called_once()
        debloated.setup_script_output.read_bytes.assert_called_once()

    def test_compare_skip(self):
        original = MagicMock(setup_script=None)
        debloated = MagicMock(setup_script=None)
        ext = HookComparator()
        assert ext.compare(original, debloated) == ComparisonResult.success(ext, debloated)
        original.setup_script_output.read_bytes.assert_not_called()
        debloated.setup_script_output.read_bytes.assert_not_called()

    def test_compare_returncode(self):
        original = MagicMock()
        original.setup_script.returncode = 0
        original.setup_script_output.read_bytes.return_value = b'hello'

        debloated = MagicMock()
        debloated.setup_script.returncode = 1
        debloated.setup_script_output.read_bytes.return_value = b'hello'

        ext = HookComparator()
        result = ext.compare(original, debloated)
        assert result.status is ComparisonStatus.error
        assert result.comparator is ext.id
        assert result.trace_directory is debloated.cwd

    def test_compare_output(self):
        original = MagicMock()
        original.setup_script.returncode = 0
        original.setup_script_output.read_bytes.return_value = b'hello'

        debloated = MagicMock()
        debloated.setup_script.returncode = 0
        debloated.setup_script_output.read_bytes.return_value = b'goodbye'

        ext = HookComparator()
        result = ext.compare(original, debloated)
        assert result.status is ComparisonStatus.error
        assert result.comparator is ext.id
        assert result.trace_directory is debloated.cwd


class TestSetupScriptComparator:
    def test_get_output(self):
        trace = MagicMock()
        ext = primitives.SetupScriptComparator({})
        assert ext.id == 'setup_script'
        assert ext.get_output(trace) == (trace.setup_script, trace.setup_script_output)


class TestTeardownScriptComparator:
    def test_get_output(self):
        trace = MagicMock()
        ext = primitives.TeardownScriptComparator({})
        assert ext.id == 'teardown_script'
        assert ext.get_output(trace) == (trace.teardown_script, trace.teardown_script_output)


class TestConcurrentScriptComparator:
    @patch.object(primitives, 'CompletedProcess')
    def test_get_output(self, mock_proc):
        trace = MagicMock()
        ext = primitives.ConcurrentScriptComparator({})
        assert ext.id == 'concurrent_script'
        assert ext.get_output(trace) == (mock_proc.return_value, trace.concurrent_script_output)
        mock_proc.assert_called_once_with(
            trace.concurrent_script.args, trace.concurrent_script.returncode
        )

    def test_get_output_none(self):
        trace = MagicMock(concurrent_script=None)
        ext = primitives.ConcurrentScriptComparator({})
        assert ext.get_output(trace) == (None, trace.concurrent_script_output)
