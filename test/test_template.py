from unittest.mock import patch

from differ import template


class TestQuoteFilter:
    @patch.object(template.shlex, 'quote')
    def test_quote_filter_call(self, mock_quote):
        s = object()
        assert template.quote_filter(s) is mock_quote.return_value
        mock_quote.assert_called_once_with(s)

    def test_quote_filter_template(self):
        templ = template.JINJA_ENVIRONMENT.from_string('hello {{name | quote}}')
        assert templ.render(name='duke leto') == "hello 'duke leto'"
