from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

from differ import core


class MockComparator(core.Comparator):
    id = 'mock_comparator'

    def __init__(self):
        super().__init__({})


class TestProject:
    @patch.object(core, 'open', new_callable=mock_open)
    @patch.object(core.yaml, 'safe_dump')
    def test_save_report(self, mock_yaml_dump, mock_file):
        trace = MagicMock()
        trace.process.args = ['prog', 'x', 'y']

        results = [
            MagicMock(comparator=MockComparator()),
            MagicMock(comparator='mock_comparator_str'),
        ]

        project = core.Project('proj', Path('/'), Path('original'))
        project.report_filename = MagicMock()

        project.save_report(trace, results)
        mock_yaml_dump.assert_called_once_with(
            {
                'values': trace.context.values,
                'trace_directory': str(trace.cwd),
                'arguments': trace.process.args[1:],
                'binary': str(trace.binary.readlink.return_value),
                'results': [
                    {
                        'comparator': 'mock_comparator',
                        'details': results[0].details,
                        'status': results[0].status.value,
                    },
                    {
                        'comparator': 'mock_comparator_str',
                        'details': results[1].details,
                        'status': results[1].status.value,
                    },
                ],
            }
        )
        project.report_filename.assert_called_once_with(trace, True)
        mock_file.assert_called_once_with(project.report_filename.return_value, 'w')
        handle = mock_file()
        handle.write.assert_called_once_with(mock_yaml_dump.return_value)

    @patch.object(core, 'open', new_callable=mock_open)
    @patch.object(core.yaml, 'safe_dump')
    def test_save_report_error(self, mock_yaml_dump, mock_file):
        trace = MagicMock(process=None)
        trace.arguments = 'x y'

        results = [
            MagicMock(comparator=MockComparator()),
            MagicMock(comparator='mock_comparator_str'),
        ]

        setattr(results[0], '__bool__', MagicMock(return_value=False))
        setattr(results[1], '__bool__', MagicMock(return_value=True))

        project = core.Project('proj', Path('/'), Path('original'))
        project.report_filename = MagicMock()

        project.save_report(trace, results)
        mock_yaml_dump.assert_called_once_with(
            {
                'values': trace.context.values,
                'trace_directory': str(trace.cwd),
                'arguments': ['x', 'y'],
                'binary': str(trace.binary.readlink.return_value),
                'results': [
                    {
                        'comparator': 'mock_comparator',
                        'details': results[0].details,
                        'status': results[0].status.value,
                    },
                    {
                        'comparator': 'mock_comparator_str',
                        'details': results[1].details,
                        'status': results[1].status.value,
                    },
                ],
            }
        )
        project.report_filename.assert_called_once_with(trace, False)
        mock_file.assert_called_once_with(project.report_filename.return_value, 'w')
        handle = mock_file()
        handle.write.assert_called_once_with(mock_yaml_dump.return_value)

    def test_report_filename(self):
        trace = MagicMock(debloater_engine='engine', context=MagicMock(id='id'))
        project = core.Project('proj', Path('/'), Path('original'))
        assert (
            project.report_filename(trace, True)
            == project.directory / 'report-engine-success-id.yml'
        )
        assert (
            project.report_filename(trace, False)
            == project.directory / 'report-engine-error-id.yml'
        )

    def test_paths(self):
        context = MagicMock()
        context.id = 'blah'
        trace = MagicMock(debloater_engine='chisel', context=context)
        project = core.Project('proj', Path('/'), Path('original'))
        assert project.context_directory(context) == Path('/') / 'trace-blah'
        assert project.trace_directory(context, 'chisel') == Path('/') / 'trace-blah' / 'chisel'
        assert project.crash_filename(trace) == Path('/') / 'crash-chisel-blah.yml'
