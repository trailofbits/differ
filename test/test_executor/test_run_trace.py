import os
from pathlib import Path
from unittest.mock import MagicMock, call, patch

from differ import executor


class TestExecutorRunTrace:
    @patch.object(executor.subprocess, 'Popen')
    @patch.object(executor.os, 'waitpid')
    @patch.object(executor.time, 'sleep')
    @patch.object(executor.subprocess, 'run')
    def test_full_run(self, mock_run, mock_sleep, mock_waitpid, mock_popen):
        pid = mock_popen.return_value.pid = 100
        setup = Path('/path/to/setup.sh')
        teardown = Path('/path/to/teardown.sh')
        app = executor.Executor(Path('/'))
        app.create_stdin_file = MagicMock()
        app.write_hook_scripts = MagicMock(return_value=[setup, teardown])
        trace = MagicMock()

        hook = MagicMock()
        trace.context.template.hooks = [hook]
        trace.context.arguments = 'hello world'
        trace.context.template.timeout.seconds = 60
        mock_waitpid.side_effect = [(0, 0), (pid, 10 << 8)]

        app.run_trace(MagicMock(), trace)

        hook.setup.assert_called_once_with(trace)
        app.create_stdin_file.assert_called_once_with(trace)
        mock_popen.assert_called_once_with(
            [str(trace.binary), 'hello', 'world'],
            cwd=str(trace.cwd),
            stdout=trace.stdout_path.open.return_value,
            stderr=trace.stderr_path.open.return_value,
            stdin=app.create_stdin_file.return_value.open.return_value,
        )
        assert trace.process is mock_popen.return_value
        assert mock_waitpid.call_args_list == [call(pid, os.WNOHANG), call(pid, os.WNOHANG)]
        assert mock_sleep.call_args_list == [call(0.001), call(0.001)]
        assert trace.process_status == 10 << 8
        assert trace.process.returncode == 10
        hook.teardown.assert_called_once_with(trace)

        app.write_hook_scripts.assert_called_once_with(trace)
        assert mock_run.call_args_list == [
            call([str(setup)], cwd=str(trace.cwd)),
            call([str(teardown)], cwd=str(trace.cwd)),
        ]

    @patch.object(executor.time, 'monotonic')
    @patch.object(executor.os, 'waitpid')
    @patch.object(executor.subprocess, 'Popen')
    def test_timeout(self, mock_popen, mock_waitpid, mock_time):
        mock_time.side_effect = [0, 10]
        pid = mock_popen.return_value.pid = 100
        mock_waitpid.return_value = (pid, 10 << 8)

        trace = MagicMock()

        trace.context.template.hooks = []
        trace.context.arguments = 'hello world'
        trace.context.template.timeout.seconds = 10

        app = executor.Executor(Path('/'))
        app.create_stdin_file = MagicMock()
        app.write_hook_scripts = MagicMock(return_value=(None, None))

        app.run_trace(MagicMock(), trace)

        assert trace.process is mock_popen.return_value
        trace.process.terminate.assert_called_once()
        mock_waitpid.assert_called_once_with(pid, 0)
        assert trace.timed_out is True
        assert trace.process_status == 10 << 8
        assert trace.process.returncode == 10
