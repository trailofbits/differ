from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from differ import executor


class TestExecutorRunProject:
    def test_run_project_error_count(self):
        template = MagicMock()
        context = MagicMock()
        project = MagicMock(templates=[template], debloaters={'x': MagicMock()})
        project.directory.exists.return_value = False

        app = executor.Executor(Path('/'))
        app.generate_contexts = MagicMock(return_value=[context])
        app.run_context = MagicMock(return_value=1)

        assert app.run_project(project) == 1
        project.directory.mkdir.assert_called_once()
        app.generate_contexts.assert_called_once_with(project, template)
        app.run_context.assert_called_once_with(project, context)

    def test_run_project_exists(self):
        project = MagicMock(templates=[], debloaters={'x': MagicMock()})
        project.directory.exists.return_value = True

        app = executor.Executor(Path('/'))

        with pytest.raises(FileExistsError):
            app.run_project(project)

    @patch.object(executor.shutil, 'rmtree')
    def test_run_project_exists_rmtree(self, mock_rmtree):
        project = MagicMock(templates=[], debloaters={'x': MagicMock()})
        project.directory.exists.return_value = True

        app = executor.Executor(Path('/'), overwrite_existing_report=True)
        app.generate_contexts = MagicMock(return_value=[])
        app.run_context = MagicMock(return_value=0)

        assert app.run_project(project) == 0
        mock_rmtree.assert_called_once_with(project.directory)
        project.directory.mkdir.assert_called_once()

    def test_setup_root_mkdir(self):
        root = MagicMock()
        root.absolute.return_value = root
        root.exists.return_value = False
        app = executor.Executor(root)
        app.setup()
        root.mkdir.assert_called_once()
