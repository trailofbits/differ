import os
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, call, patch

from differ import executor


class TestExecutorRunTrace:
    @patch.object(executor.subprocess, 'Popen')
    def test_run_trace(self, mock_popen):
        setup = Path('/path/to/setup.sh')
        teardown = Path('/path/to/teardown.sh')

        trace_cwd = MagicMock()
        link_cwd = trace_cwd.parent / 'current_trace'
        link_cwd.exists.return_value = True
        trace = MagicMock(cwd=trace_cwd)
        trace.context.arguments = 'hello world'

        app = executor.Executor(Path('/'))
        app.create_stdin_file = MagicMock()
        app.write_hook_scripts = MagicMock(return_value=[setup, teardown])
        app._setup_trace = MagicMock()
        app._monitor_trace = MagicMock()
        app._teardown_trace = MagicMock()

        app.run_trace(MagicMock(link_filename=''), trace)

        mock_popen.assert_called_once_with(
            [f'./{trace.binary.name}', 'hello', 'world'],
            cwd=str(link_cwd),
            stdout=trace.stdout_path.open.return_value,
            stderr=trace.stderr_path.open.return_value,
            stdin=app.create_stdin_file.return_value.open.return_value,
        )

        app.write_hook_scripts.assert_called_once_with(trace)
        app.create_stdin_file.assert_called_once_with(trace)
        app._setup_trace.assert_called_once_with(trace, setup, link_cwd)
        app._teardown_trace.assert_called_once_with(trace, teardown, link_cwd)
        app._monitor_trace.assert_called_once_with(trace)

        link_cwd.exists.assert_called_once()
        assert link_cwd.unlink.call_count == 2
        link_cwd.symlink_to.assert_called_once_with(trace_cwd)

    @patch.object(executor.subprocess, 'Popen')
    def test_run_trace_link_filename(self, mock_popen):
        setup = Path('/path/to/setup.sh')
        teardown = Path('/path/to/teardown.sh')

        trace_cwd = MagicMock()
        link_cwd = trace_cwd.parent / 'current_trace'
        link_cwd.exists.return_value = False
        link_filename = trace_cwd / 'my_binary'
        trace = MagicMock(cwd=trace_cwd)
        trace.context.arguments = 'hello world'

        app = executor.Executor(Path('/'))
        app.create_stdin_file = MagicMock()
        app.write_hook_scripts = MagicMock(return_value=[setup, teardown])
        app._setup_trace = MagicMock()
        app._monitor_trace = MagicMock()
        app._teardown_trace = MagicMock()

        app.run_trace(MagicMock(link_filename='my_binary'), trace)

        mock_popen.assert_called_once_with(
            ['./my_binary', 'hello', 'world'],
            cwd=str(link_cwd),
            stdout=trace.stdout_path.open.return_value,
            stderr=trace.stderr_path.open.return_value,
            stdin=app.create_stdin_file.return_value.open.return_value,
        )

        app.write_hook_scripts.assert_called_once_with(trace)
        app.create_stdin_file.assert_called_once_with(trace)
        app._setup_trace.assert_called_once_with(trace, setup, link_cwd)
        app._teardown_trace.assert_called_once_with(trace, teardown, link_cwd)
        app._monitor_trace.assert_called_once_with(trace)

        link_cwd.exists.assert_called_once()
        link_cwd.unlink.assert_called_once()
        link_cwd.symlink_to.assert_called_once_with(trace_cwd)
        link_filename.symlink_to.assert_called_once_with(trace.binary)

    @patch.object(executor.subprocess, 'run')
    def test_setup_trace(self, mock_run):
        hook = MagicMock()
        trace = MagicMock()
        trace.context.template.hooks = [hook]

        setup = object()
        cwd = object()

        app = executor.Executor(Path('/'))
        app._setup_trace(trace, setup, cwd)

        hook.setup.assert_called_once_with(trace)
        assert trace.setup_script is mock_run.return_value
        mock_run.assert_called_once_with(
            [str(setup)],
            cwd=str(cwd),
            stdout=trace.setup_script_output.open.return_value,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
        )
        trace.setup_script_output.open.assert_called_once_with('wb')

    @patch.object(executor.subprocess, 'run')
    def test_setup_trace_no_script(self, mock_run):
        hook = MagicMock()
        trace = MagicMock(setup_script=None)
        trace.context.template.hooks = [hook]

        cwd = object()

        app = executor.Executor(Path('/'))
        app._setup_trace(trace, None, cwd)

        hook.setup.assert_called_once_with(trace)
        assert trace.setup_script is None
        mock_run.assert_not_called()

    @patch.object(executor.subprocess, 'run')
    def test_teardown_trace(self, mock_run):
        hook = MagicMock()
        trace = MagicMock()
        trace.context.template.hooks = [hook]

        teardown = object()
        cwd = object()

        app = executor.Executor(Path('/'))
        app._teardown_trace(trace, teardown, cwd)

        hook.teardown.assert_called_once_with(trace)
        mock_run.assert_called_once_with(
            [str(teardown)],
            cwd=str(cwd),
            stdout=trace.teardown_script_output.open.return_value,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
        )
        trace.teardown_script_output.open.assert_called_once_with('wb')
        trace.concurrent_script.wait.assert_called_once_with(0.001)

    def test_teardown_trace_concurrent_timeout(self):
        trace = MagicMock()
        trace.context.template.hooks = []
        trace.concurrent_script.wait.side_effect = [subprocess.TimeoutExpired('asdf', 1.0), None]

        cwd = object()

        app = executor.Executor(Path('/'))
        app._teardown_trace(trace, None, cwd)

        assert trace.concurrent_script.wait.call_args_list == [call(0.001), call()]
        trace.concurrent_script.terminate.assert_called_once()

    @patch.object(executor.subprocess, 'Popen')
    @patch.object(executor.time, 'monotonic')
    @patch.object(executor.os, 'waitstatus_to_exitcode')
    def test_monitor_trace(self, mock_exitcode, mock_time, mock_popen):
        mock_time.return_value = 10

        trace = MagicMock()
        trace.context.template.timeout.seconds = 5
        trace.context.template.concurrent = None

        app = executor.Executor(Path('/'))
        app._wait_process = MagicMock(return_value=(False, 100))

        app._monitor_trace(trace)

        app._wait_process.assert_called_once_with(trace.process, 15)  # 10 + 5
        assert trace.process_status == 100
        assert trace.process.returncode == mock_exitcode.return_value
        mock_exitcode.assert_called_once_with(100)
        mock_popen.assert_not_called()

    @patch.object(executor.subprocess, 'Popen')
    @patch.object(executor.time, 'monotonic')
    @patch.object(executor.os, 'waitstatus_to_exitcode')
    def test_monitor_trace_concurrent(self, mock_exitcode, mock_time, mock_popen):
        mock_time.return_value = 10

        trace = MagicMock()
        trace.context.template.concurrent.delay = 2
        trace.context.template.timeout.seconds = 5

        app = executor.Executor(Path('/'))
        app._wait_process = MagicMock(side_effect=[(True, 0), (False, 100)])

        app._monitor_trace(trace)

        assert app._wait_process.call_args_list == [
            call(trace.process, 12),  # 10 + 5
            call(trace.process, 15),
        ]
        assert trace.process_status == 100
        assert trace.process.returncode == mock_exitcode.return_value
        mock_exitcode.assert_called_once_with(100)
        mock_popen.assert_called_once_with(
            [str(trace.concurrent_script_path)],
            stdout=trace.concurrent_script_output.open.return_value,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
        )
        trace.concurrent_script_output.open.assert_called_once_with('wb')

    @patch.object(executor.subprocess, 'Popen')
    @patch.object(executor.time, 'monotonic')
    @patch.object(executor.os, 'waitstatus_to_exitcode')
    @patch.object(executor.os, 'waitpid')
    def test_monitor_trace_terminate(self, mock_waitpid, mock_exitcode, mock_time, mock_popen):
        mock_time.return_value = 10
        mock_waitpid.return_value = (0, 100)

        trace = MagicMock()
        trace.context.template.timeout.seconds = 5
        trace.context.template.concurrent = None

        app = executor.Executor(Path('/'))
        app._wait_process = MagicMock(return_value=(True, 0))

        app._monitor_trace(trace)

        app._wait_process.assert_called_once_with(trace.process, 15)  # 10 + 5
        assert trace.process_status == 100
        assert trace.process.returncode == mock_exitcode.return_value
        mock_exitcode.assert_called_once_with(100)
        mock_popen.assert_not_called()
        trace.process.terminate.assert_called_once()
        assert trace.timed_out is True

    @patch.object(executor.time, 'monotonic')
    @patch.object(executor.os, 'waitpid')
    @patch.object(executor.time, 'sleep')
    def test_wait_process(self, mock_sleep, mock_waitpid, mock_time):
        proc = MagicMock(pid=6)
        mock_waitpid.side_effect = [(0, 0), (6, 100)]
        mock_time.side_effect = [1, 2, 3, 4]

        app = executor.Executor(Path('/'))
        assert app._wait_process(proc, 4) == (False, 100)
        assert mock_time.call_count == 2
        assert mock_waitpid.call_args_list == [
            call(proc.pid, os.WNOHANG),
            call(proc.pid, os.WNOHANG),
        ]
        assert mock_sleep.call_args_list == [call(0.001), call(0.001)]

    @patch.object(executor.time, 'monotonic')
    @patch.object(executor.os, 'waitpid')
    @patch.object(executor.time, 'sleep')
    def test_wait_process_timeout(self, mock_sleep, mock_waitpid, mock_time):
        proc = MagicMock(pid=6)
        mock_waitpid.return_value = (0, 0)
        mock_time.side_effect = [1, 2, 3, 4]

        app = executor.Executor(Path('/'))
        assert app._wait_process(proc, 4) == (True, 0)
        assert mock_time.call_count == 4
        assert mock_waitpid.call_args_list == [
            call(proc.pid, os.WNOHANG),
            call(proc.pid, os.WNOHANG),
            call(proc.pid, os.WNOHANG),
        ]
        assert mock_sleep.call_args_list == [call(0.001), call(0.001), call(0.001)]
