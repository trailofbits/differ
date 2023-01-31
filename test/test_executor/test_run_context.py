from pathlib import Path
from unittest.mock import MagicMock, call

import pytest

from differ import executor


class TestExecutorRunContext:
    def test_run_context_directory_exists(self):
        context = MagicMock()
        project = MagicMock()
        context_dir = project.context_directory.return_value = MagicMock()
        context_dir.exists.return_value = True
        app = executor.Executor(Path('/'))

        with pytest.raises(FileExistsError):
            app.run_context(project, context)

        project.context_directory.assert_called_once_with(context)

    def test_run_context_check_original_trace_crash(self):
        crash = MagicMock()
        project = MagicMock()
        context = MagicMock()
        trace = MagicMock()
        context_dir = project.context_directory.return_value
        context_dir.exists.return_value = False

        app = executor.Executor(Path('/'))
        app.check_original_trace = MagicMock(return_value=crash)
        app.create_trace = MagicMock(return_value=trace)
        app.run_trace = MagicMock()

        assert app.run_context(project, context) == 1
        crash.save.assert_called_once_with(project.crash_filename.return_value)
        project.crash_filename.assert_called_once_with(trace)
        app.create_trace.assert_called_once_with(
            project, context, project.original, '__original__'
        )
        app.run_trace(project, trace)
        app.check_original_trace.assert_called_once_with(project, trace)
        context_dir.mkdir.assert_called_once()

    def test_run_context_save_report(self):
        debloater = MagicMock()
        project = MagicMock(debloaters={'x': debloater})
        context = MagicMock()
        context_dir = project.context_directory.return_value
        context_dir.exists.return_value = False

        errors = [MagicMock()]
        original_trace = MagicMock()
        debloated_trace = MagicMock()
        debloated_trace.context.template.expect_success = True

        app = executor.Executor(Path('/'))
        app.create_trace = MagicMock(side_effect=[original_trace, debloated_trace])
        app.run_trace = MagicMock()
        app.check_original_trace = MagicMock(return_value=None)
        app.compare_trace = MagicMock(return_value=errors)
        app.check_trace_crash = MagicMock(return_value=None)
        app.get_errors = MagicMock(return_value=errors)

        assert app.run_context(project, context) == 1
        project.save_report.assert_called_once_with(debloated_trace, errors)
        app.compare_trace.assert_called_once_with(project, original_trace, debloated_trace)
        app.check_trace_crash.assert_called_once_with(debloated_trace)
        app.get_errors.assert_called_once_with(debloated_trace, errors, None)
        assert app.create_trace.call_args_list == [
            call(project, context, project.original, '__original__'),
            call(project, context, debloater.binary, debloater.engine),
        ]

        context.save.assert_called_once_with(context_dir / 'context.yml')

    def test_run_context_save_crash(self):
        debloater = MagicMock()
        project = MagicMock(debloaters={'x': debloater})
        context = MagicMock()
        context_dir = project.context_directory.return_value
        context_dir.exists.return_value = False
        crash = MagicMock()

        original_trace = MagicMock()
        debloated_trace = MagicMock()
        debloated_trace.context.template.expect_success = True

        app = executor.Executor(Path('/'))
        app.create_trace = MagicMock(side_effect=[original_trace, debloated_trace])
        app.run_trace = MagicMock()
        app.check_original_trace = MagicMock(return_value=None)
        app.compare_trace = MagicMock(return_value=[])
        app.check_trace_crash = MagicMock(return_value=crash)
        app.get_errors = MagicMock(return_value=[])

        assert app.run_context(project, context) == 1
        crash.save.assert_called_once_with(project.crash_filename.return_value)
        project.crash_filename.assert_called_once_with(debloated_trace)
        app.compare_trace.assert_called_once_with(project, original_trace, debloated_trace)
        app.check_trace_crash.assert_called_once_with(debloated_trace)
        app.get_errors.assert_called_once_with(debloated_trace, [], crash)
