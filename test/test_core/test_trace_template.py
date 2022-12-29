from unittest.mock import call, patch

from differ import core


class TestTraceTemplate:
    @patch.object(core, 'JINJA_ENVIRONMENT')
    def test_script_exit_on_first_error_enabled(self, mock_env):
        template = core.TraceTemplate(
            setup='hello', concurrent=core.ConcurrentHook('world'), teardown='goodbye'
        )
        assert template.setup_template is mock_env.from_string.return_value
        assert template.concurrent_template is mock_env.from_string.return_value
        assert template.teardown_template is mock_env.from_string.return_value

        assert mock_env.from_string.call_args_list == [
            call('set -e\n\nhello'),
            call('set -e\n\nworld'),
            call('set -e\n\ngoodbye'),
        ]

    @patch.object(core, 'JINJA_ENVIRONMENT')
    def test_script_exit_on_first_error_enabled_empty(self, mock_env):
        template = core.TraceTemplate()
        assert template.setup_template is None
        assert template.concurrent_template is None
        assert template.teardown_template is None
        mock_env.from_string.assert_not_called()

    @patch.object(core, 'JINJA_ENVIRONMENT')
    def test_script_exit_on_first_error_disabled(self, mock_env):
        template = core.TraceTemplate(
            setup='hello',
            concurrent=core.ConcurrentHook('world'),
            teardown='goodbye',
            script_exit_on_first_error=False,
        )
        assert template.setup_template is mock_env.from_string.return_value
        assert template.concurrent_template is mock_env.from_string.return_value
        assert template.teardown_template is mock_env.from_string.return_value

        assert mock_env.from_string.call_args_list == [
            call('hello'),
            call('world'),
            call('goodbye'),
        ]
