from differ.core import TraceTemplate
from differ.parameters import CombinationParameterGenerator
from differ.variables.primitives import IntVariable, StringVariable


class TestCombinationParameterGenerator:
    def test_combination(self):
        template = TraceTemplate(
            variables={
                'color': StringVariable('color', {'values': ['red', 'blue', 'green']}),
                'saturation': IntVariable('saturation', {'values': [0, 50, 100]}),
                'factor': IntVariable('factor', {'values': [1, 2]}),
            }
        )
        generator = CombinationParameterGenerator(template)
        assert list(generator.generate()) == [
            # red
            {'color': 'red', 'saturation': 0, 'factor': 1},
            {'color': 'red', 'saturation': 0, 'factor': 2},
            {'color': 'red', 'saturation': 50, 'factor': 1},
            {'color': 'red', 'saturation': 50, 'factor': 2},
            {'color': 'red', 'saturation': 100, 'factor': 1},
            {'color': 'red', 'saturation': 100, 'factor': 2},
            # blue
            {'color': 'blue', 'saturation': 0, 'factor': 1},
            {'color': 'blue', 'saturation': 0, 'factor': 2},
            {'color': 'blue', 'saturation': 50, 'factor': 1},
            {'color': 'blue', 'saturation': 50, 'factor': 2},
            {'color': 'blue', 'saturation': 100, 'factor': 1},
            {'color': 'blue', 'saturation': 100, 'factor': 2},
            # green
            {'color': 'green', 'saturation': 0, 'factor': 1},
            {'color': 'green', 'saturation': 0, 'factor': 2},
            {'color': 'green', 'saturation': 50, 'factor': 1},
            {'color': 'green', 'saturation': 50, 'factor': 2},
            {'color': 'green', 'saturation': 100, 'factor': 1},
            {'color': 'green', 'saturation': 100, 'factor': 2},
        ]
