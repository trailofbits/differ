from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from differ import executor


class TestExecutorGenerateTraces:
    @patch.object(executor, 'Trace')
    def test_create_trace(self, mock_trace_cls):
        project = MagicMock()
        context = MagicMock(values={'x': 1, 'y': 2})
        binary = MagicMock()
        engine = '_engine_'
        trace = mock_trace_cls.return_value

        cwd = project.trace_directory.return_value = MagicMock()
        cwd.exists.return_value = False

        app = executor.Executor(Path('/'))
        assert app.create_trace(project, context, binary, engine) is trace
        project.trace_directory.assert_called_once_with(context, engine)
        cwd.mkdir.assert_called_once()
        link = cwd / binary.name
        link.symlink_to.assert_called_once_with(binary)
        mock_trace_cls.assert_called_once_with(link, context, cwd, engine)
        assert trace.arguments is context.template.arguments_template.render.return_value
        context.template.arguments_template.render.assert_called_once_with(
            trace=trace, **context.values
        )

    @patch.object(executor, 'Trace')
    def test_create_trace_error(self, mock_trace_cls):
        project = MagicMock()
        context = MagicMock()
        binary = MagicMock()
        engine = '_engine_'

        cwd = project.trace_directory.return_value = MagicMock()
        cwd.exists.return_value = True

        app = executor.Executor(Path('/'))

        with pytest.raises(FileExistsError):
            app.create_trace(project, context, binary, engine)

        project.trace_directory.assert_called_once_with(context, engine)

    @patch.object(executor, 'CombinationParameterGenerator')
    def test_generate_paramter(self, mock_param_gen_cls):
        template = MagicMock()
        value_sets = [{'x': 1}, {'y': 2}]
        param_gen = mock_param_gen_cls.return_value
        param_gen.generate.return_value = value_sets

        app = executor.Executor(Path('/'))
        assert app.generate_parameters(template) == value_sets
        mock_param_gen_cls.assert_called_once_with(template)
        param_gen.generate.assert_called_once()

    @patch.object(executor, 'CombinationParameterGenerator')
    def test_generate_paramter_max(self, mock_param_gen_cls):
        template = MagicMock()
        value_sets = [{'x': 1}, {'y': 2}]
        param_gen = mock_param_gen_cls.return_value
        param_gen.generate.return_value = value_sets

        app = executor.Executor(Path('/'), max_permutations=1)
        assert app.generate_parameters(template) == [value_sets[0]]
        mock_param_gen_cls.assert_called_once_with(template)
        param_gen.generate.assert_called_once()
