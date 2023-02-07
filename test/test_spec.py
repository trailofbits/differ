import sys
from pathlib import Path
from unittest.mock import MagicMock, call, patch

from differ.spec import REPORT_DIR, main


class TestSpec:
    @patch('argparse.ArgumentParser')
    @patch('csv.writer')
    @patch('differ.spec.discover_projects')
    def test_main(self, mock_discover, mock_writer_cls, mock_parser_cls):
        writer = mock_writer_cls.return_value
        out_filename = MagicMock()
        output = out_filename.open.return_value
        parser = mock_parser_cls.return_value
        parser.parse_args.return_value = MagicMock(project=None, output=out_filename)

        template = MagicMock()
        project = MagicMock(templates=[template])
        mock_discover.return_value = [project]

        main()

        mock_discover.assert_called_once_with()
        out_filename.open.assert_called_once_with('w', newline='')
        mock_writer_cls.assert_called_once_with(output)
        assert writer.writerow.call_args_list == [
            call(('binary', 'version', 'name', 'arguments', 'stdin', 'summary')),
            call(
                (
                    project.name,
                    project.version,
                    template.name,
                    template.arguments,
                    'yes',
                    template.summary,
                )
            ),
        ]
        output.close.assert_called_once_with()

    @patch('argparse.ArgumentParser')
    @patch('csv.writer')
    @patch('differ.spec.discover_projects')
    @patch('differ.core.Project.load')
    def test_main_project_stdout(self, mock_load, mock_discover, mock_writer_cls, mock_parser_cls):
        writer = mock_writer_cls.return_value
        parser = mock_parser_cls.return_value
        parser.parse_args.return_value = MagicMock(project=[Path('project.yml')], output=None)

        template = MagicMock(stdin=None)
        project = MagicMock(templates=[template])
        mock_load.return_value = project

        main()

        mock_discover.assert_not_called()
        mock_writer_cls.assert_called_once_with(sys.stdout)
        assert writer.writerow.call_args_list == [
            call(('binary', 'version', 'name', 'arguments', 'stdin', 'summary')),
            call(
                (
                    project.name,
                    project.version,
                    template.name,
                    template.arguments,
                    'no',
                    template.summary,
                )
            ),
        ]
        mock_load.assert_called_once_with(REPORT_DIR, Path('project.yml'))
