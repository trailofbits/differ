from pathlib import Path
from unittest.mock import MagicMock

from differ import executor


class TestExecutorCompareTrace:
    def test_compare_trace(self):
        project = MagicMock()
        original = MagicMock()
        debloated = MagicMock()
        comparator = MagicMock()

        original.context.template.comparators = [comparator]

        app = executor.Executor(Path('/'))
        app.compare_trace(project, original, debloated) == [comparator.compare.return_value]
        comparator.compare.assert_called_once_with(original, debloated)
