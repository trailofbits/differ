from unittest.mock import MagicMock

from differ.comparators import primitives
from differ.core import ComparisonResult, ComparisonStatus


class TestExitCodeComparator:
    def test_verify_original_skip(self):
        trace = MagicMock()
        ext = primitives.ExitCodeComparator({})
        assert ext.verify_original(trace) is None

    def test_verify_original_ok(self):
        trace = MagicMock()
        trace.process.returncode = 1
        ext = primitives.ExitCodeComparator({})
        assert ext.verify_original(trace) is None

    def test_verify_original_error(self):
        trace = MagicMock()
        trace.process.returncode = 1
        ext = primitives.ExitCodeComparator({'expect': 0})
        result = ext.verify_original(trace)
        assert result is not None
        assert result.comparator is ext
        assert result.trace is trace

    def test_verify_original_coerce_error(self):
        trace = MagicMock()
        trace.process.returncode = 1
        ext = primitives.ExitCodeComparator({'expect': True})
        result = ext.verify_original(trace)
        assert result is not None
        assert result.comparator is ext
        assert result.trace is trace

    def test_verify_original_coerce_ok(self):
        trace = MagicMock()
        trace.process.returncode = 1
        ext = primitives.ExitCodeComparator({'expect': False})
        assert ext.verify_original(trace) is None

    def test_compare_ok(self):
        original = MagicMock()
        original.process.returncode = 0

        debloated = MagicMock()
        debloated.process.returncode = 0

        ext = primitives.ExitCodeComparator({})
        assert ext.compare(original, debloated).status is ComparisonStatus.success

    def test_compare_coerce_ok(self):
        original = MagicMock()
        original.process.returncode = 1

        debloated = MagicMock()
        debloated.process.returncode = 2

        ext = primitives.ExitCodeComparator({'expect': False})
        assert ext.compare(original, debloated).status is ComparisonStatus.success

    def test_compare_error(self):
        original = MagicMock()
        original.process.returncode = 0

        debloated = MagicMock()
        debloated.process.returncode = 1

        ext = primitives.ExitCodeComparator({})
        result = ext.compare(original, debloated)
        assert result == ComparisonResult.error(ext, debloated, result.details)

    def test_compare_coerce_error(self):
        original = MagicMock()
        original.process.returncode = 0

        debloated = MagicMock()
        debloated.process.returncode = 1

        ext = primitives.ExitCodeComparator({'expect': True})
        result = ext.compare(original, debloated)
        assert result == ComparisonResult.error(ext, debloated, result.details)
