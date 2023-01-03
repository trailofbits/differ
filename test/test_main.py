from pathlib import Path
from unittest.mock import patch

from differ.__main__ import main


class TestMain:
    @patch('argparse.ArgumentParser')
    @patch('differ.executor.Executor')
    @patch('differ.core.Project')
    def test_main(self, mock_project_cls, mock_executor_cls, mock_parser_cls):
        parser = mock_parser_cls.return_value
        args = parser.parse_args.return_value
        args.report_dir = '/asdf'
        project = mock_project_cls.load.return_value
        app = mock_executor_cls.return_value
        app.run_project.return_value = 10

        assert main() is app.run_project.return_value

        mock_executor_cls.assert_called_once_with(
            Path(args.report_dir),
            report_successes=args.report_successes,
            max_permutations=args.max_permutations,
            verbose=args.verbose,
            overwrite_existing_report=args.force,
        )
        app.setup.assert_called_once()
        mock_project_cls.load.assert_called_once_with(app.root, args.project_filename)
        app.run_project.assert_called_once_with(project)
