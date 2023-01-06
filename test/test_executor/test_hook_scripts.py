from pathlib import Path
from unittest.mock import MagicMock, call, mock_open, patch

from differ import executor


class TestExecutorHookScripts:
    @patch.object(executor, 'open', new_callable=mock_open)
    @patch.object(executor.os, 'chmod')
    def test_write_hook_scripts(self, mock_chmod, mock_file):
        trace = MagicMock()
        values = trace.context.values = {'x': 1}

        app = executor.Executor(Path('/'))
        app.write_hook_scripts(trace)

        trace.context.template.setup_template.render.assert_called_once_with(trace=trace, **values)
        trace.context.template.teardown_template.render.assert_called_once_with(
            trace=trace, **values
        )
        trace.context.template.concurrent_template.render.assert_called_once_with(
            trace=trace, **values
        )
        assert mock_file.call_args_list == [
            call(trace.setup_script_path, 'w'),
            call(trace.concurrent_script_path, 'w'),
            call(trace.teardown_script_path, 'w'),
        ]
        handle = mock_file()
        handle.write.assert_has_calls(
            [
                call(str(trace.context.template.setup_template.render.return_value)),
                call(str(trace.context.template.concurrent_template.render.return_value)),
                call(str(trace.context.template.teardown_template.render.return_value)),
            ],
            any_order=True,
        )
        assert mock_chmod.call_args_list == [
            call(trace.setup_script_path, 0o755),
            call(trace.concurrent_script_path, 0o755),
            call(trace.teardown_script_path, 0o755),
        ]

    def test_write_hook_scripts_empty(self):
        trace = MagicMock()
        trace.context.template.setup_template = None
        trace.context.template.teardown_template = None
        trace.context.template.concurrent_template = None

        app = executor.Executor(Path('/'))
        app.write_hook_scripts(trace)
