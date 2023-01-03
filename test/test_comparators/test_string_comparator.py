from unittest.mock import MagicMock, patch

from differ.comparators import primitives
from differ.core import ComparisonResult, ComparisonStatus


class StringComparator(primitives.StringComparator):
    STRING_FIELD_NAME = 'field'

    def get_string(self, trace) -> bytes:
        return trace.read_stdout()


class TestStringComparator:
    def test_compare_exact(self):
        comparator = StringComparator({})
        original = MagicMock()
        original.read_stdout.return_value = b'asdf'
        debloated = MagicMock()
        debloated.read_stdout.return_value = b'asdf'

        result = comparator.compare(original, debloated)
        assert result == ComparisonResult.success(comparator, debloated, result.details)

    def test_compare_exact_error(self):
        comparator = StringComparator({})
        original = MagicMock()
        original.read_stdout.return_value = b'asdf'
        debloated = MagicMock()
        debloated.read_stdout.return_value = b'asdf2'

        result = comparator.compare(original, debloated)
        assert result == ComparisonResult.error(comparator, debloated, result.details)

    def test_compare_regex(self):
        comparator = StringComparator({'pattern': '^hello, [A-Z][a-z]+$'})
        original = MagicMock()
        original.read_stdout.return_value = b'hello, Adam'
        debloated = MagicMock()
        debloated.read_stdout.return_value = b'hello, Bob'

        result = comparator.compare(original, debloated)
        assert result == ComparisonResult.success(comparator, debloated, result.details)

    def test_compare_regex_error(self):
        comparator = StringComparator({'pattern': '^hello, [A-Z][a-z]+$'})
        original = MagicMock()
        original.read_stdout.return_value = b'hello, Adam'
        debloated = MagicMock()
        debloated.read_stdout.return_value = b'hello, X-91b'

        result = comparator.compare(original, debloated)
        assert result == ComparisonResult.error(comparator, debloated, result.details)

    def test_compare_original_exact(self):
        comparator = StringComparator({})
        assert comparator.verify_original(MagicMock()) is None

    def test_compare_original_pattern(self):
        comparator = StringComparator({'pattern': '^hello, [A-Z][a-z]+$'})
        original = MagicMock()
        original.read_stdout.return_value = b'hello, Adam'

        assert comparator.verify_original(original) is None

    def test_compare_original_pattern_error(self):
        comparator = StringComparator({'pattern': '^hello, [A-Z][a-z]+$'})
        original = MagicMock()
        original.read_stdout.return_value = b'hello, '

        result = comparator.verify_original(original)
        assert result is not None
        assert result.comparator is comparator
        assert result.trace is original
