from unittest.mock import MagicMock, patch

import pytest

from differ.parameters import CombinationParameterGenerator, ParameterIterator


class TestParameterIterator:
    def test_advance(self):
        template = MagicMock()
        variable = MagicMock()
        variable.generate_values.return_value = iter([1, 2])

        it = ParameterIterator(template, variable)
        assert it.value == 1
        assert not it.advance()
        assert it.value == 2
        assert it.advance()
        assert it.value == 1
        assert not it.advance()
        assert it.value == 2
        assert it.advance()

        variable.generate_values.assert_called_once_with(template)


class TestCombinationParameterGenerator:
    def test_generate(self):
        var1 = MagicMock()
        var1.name = 'int'
        var1.generate_values.return_value = iter([1, 2])

        var2 = MagicMock()
        var2.name = 'str'
        var2.generate_values.return_value = iter(['a', 'b', 'c'])

        template = MagicMock()
        template.variables.values.return_value = [var1, var2]

        gen = CombinationParameterGenerator(template)
        it = gen.generate()

        assert next(it) == {'int': 1, 'str': 'a'}
        assert next(it) == {'int': 1, 'str': 'b'}
        assert next(it) == {'int': 1, 'str': 'c'}
        assert next(it) == {'int': 2, 'str': 'a'}
        assert next(it) == {'int': 2, 'str': 'b'}
        assert next(it) == {'int': 2, 'str': 'c'}

        with pytest.raises(StopIteration):
            next(it)

    def test_generate_list(self):
        var1 = MagicMock()
        var1.name = 'int'
        var1.generate_values.return_value = iter([1, 2])

        var2 = MagicMock()
        var2.name = 'str'
        var2.generate_values.return_value = iter(['a', 'b', 'c'])

        template = MagicMock()
        template.variables.values.return_value = [var1, var2]

        gen = CombinationParameterGenerator(template)
        assert list(gen.generate()) == [
            {'int': 1, 'str': 'a'},
            {'int': 1, 'str': 'b'},
            {'int': 1, 'str': 'c'},
            {'int': 2, 'str': 'a'},
            {'int': 2, 'str': 'b'},
            {'int': 2, 'str': 'c'},
        ]
