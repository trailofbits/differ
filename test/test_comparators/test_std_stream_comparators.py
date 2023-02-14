from unittest.mock import MagicMock

from differ.comparators import primitives


class TestStdstreamComparators:
    def test_stdout_get_string(self):
        trace = MagicMock()
        cmp = primitives.StdoutComparator({})
        assert cmp.get_string(trace) is trace.read_stdout.return_value

    def test_stderr_get_string(self):
        trace = MagicMock()
        cmp = primitives.StderrComparator({})
        assert cmp.get_string(trace) is trace.read_stderr.return_value
