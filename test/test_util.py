from unittest.mock import MagicMock, call, patch

from differ.util import discover_projects


class TestUtil:
    @patch('differ.core.Project.load')
    def test_discover_projects(self, mock_load):
        report_dir = object()
        project = MagicMock()
        mock_load.side_effect = [ValueError(), project]
        root = MagicMock()
        project_dir = MagicMock()
        project_dir.is_dir.return_value = True
        project_files = project_dir.iterdir.return_value = [
            MagicMock(suffix='.txt'),
            MagicMock(suffix='.yml'),
            MagicMock(suffix='.yaml'),
        ]
        root.iterdir.return_value = [MagicMock(is_dir=MagicMock(return_value=False)), project_dir]

        assert discover_projects(root, report_dir) == [project]
        assert mock_load.call_args_list == [
            call(report_dir, project_files[1]),
            call(report_dir, project_files[2]),
        ]
