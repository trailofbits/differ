import os
import subprocess
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

        trace_cwd = MagicMock()
        link_cwd = trace_cwd.parent / 'current_trace'
        link_cwd.exists.return_value = True
        trace = MagicMock(cwd=trace_cwd)

        hook = MagicMock()
        trace.context.template.hooks = [hook]
        trace.context.arguments = 'hello world'
        trace.context.template.timeout.seconds = 60
        mock_waitpid.side_effect = [(0, 0), (pid, 10 << 8)]

        app.run_trace(MagicMock(link_filename=''), trace)

        hook.setup.assert_called_once_with(trace)
        app.create_stdin_file.assert_called_once_with(trace)
        mock_popen.assert_called_once_with(
            [f'./{trace.binary.name}', 'hello', 'world'],
            cwd=str(link_cwd),
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
            call(
                [str(setup)],
                cwd=str(link_cwd),
                stdout=trace.setup_script_output.open.return_value,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
            ),
            call(
                [str(teardown)],
                cwd=str(link_cwd),
                stdout=trace.teardown_script_output.open.return_value,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
            ),
        ]

        link_cwd.exists.assert_called_once()
        assert link_cwd.unlink.call_count == 2
        link_cwd.symlink_to.assert_called_once_with(trace_cwd)

    @patch.object(executor.subprocess, 'Popen')
    @patch.object(executor.os, 'waitpid')
    @patch.object(executor.time, 'sleep')
    @patch.object(executor.subprocess, 'run')
    def test_full_run_link_filename(self, mock_run, mock_sleep, mock_waitpid, mock_popen):
        pid = mock_popen.return_value.pid = 100
        setup = Path('/path/to/setup.sh')
        teardown = Path('/path/to/teardown.sh')
        app = executor.Executor(Path('/'))
        app.create_stdin_file = MagicMock()
        app.write_hook_scripts = MagicMock(return_value=[setup, teardown])

        trace_cwd = MagicMock()
        link_cwd = trace_cwd.parent / 'current_trace'
        link_cwd.exists.return_value = True
        trace = MagicMock(cwd=trace_cwd)

        link_target = trace_cwd / 'my_binary'

        hook = MagicMock()
        trace.context.template.hooks = [hook]
        trace.context.arguments = 'hello world'
        trace.context.template.timeout.seconds = 60
        mock_waitpid.side_effect = [(0, 0), (pid, 10 << 8)]

        app.run_trace(MagicMock(link_filename='my_binary'), trace)

        hook.setup.assert_called_once_with(trace)
        app.create_stdin_file.assert_called_once_with(trace)
        mock_popen.assert_called_once_with(
            ['./my_binary', 'hello', 'world'],
            cwd=str(link_cwd),
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
            call(
                [str(setup)],
                cwd=str(link_cwd),
                stdout=trace.setup_script_output.open.return_value,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
            ),
            call(
                [str(teardown)],
                cwd=str(link_cwd),
                stdout=trace.teardown_script_output.open.return_value,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
            ),
        ]

        link_cwd.exists.assert_called_once()
        link_cwd.symlink_to.assert_called_once_with(trace_cwd)
        assert link_cwd.unlink.call_count == 2
        link_target.symlink_to.assert_called_once_with(trace.binary)

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
