from differ.core import TraceTemplate
from differ.variables.primitives import IntVariable

"""
You could also add unit tests that exercise the generate_values
function to make sure we honor both self.values and the rexex generation.
"""


def getConfig() -> dict:
    configs = [
        {'values': [1, 2], 'range': {'minimum': 3, 'maximum': 99, 'count': 5}},
        {'values': [4, 7, 8, 9], 'range': {'minimum': 10, 'maximum': 1000, 'count': 90}},
        {'values': [], 'range': {'minimum': 11, 'maximum': 12, 'count': 1}},
        {'values': [], 'range': {'minimum': 2, 'maximum': 4, 'count': 2}},
    ]
    for config in configs:
        yield config


def getName() -> str:
    for x in range(100):
        yield str(x)


CONFIG_GENERATOR = getConfig()


def test_intvar1():
    intVar = IntVariable(name=getName(), config=next(CONFIG_GENERATOR))
    generatedExps = intVar.generate_values(TraceTemplate())
    for x in generatedExps:
        assert x == 1 or x == 2 or (x <= intVar.maximum and x >= intVar.minimum)


def test_intvar2():
    intVar = IntVariable(name=getName(), config=next(CONFIG_GENERATOR))
    generatedExps = intVar.generate_values(TraceTemplate())
    for x in generatedExps:
        assert (
            x == 4 or x == 7 or x == 8 or x == 9 or (x <= intVar.maximum and x >= intVar.minimum)
        )


def test_intvar3():
    intVar = IntVariable(name=getName(), config=next(CONFIG_GENERATOR))
    generatedExps = intVar.generate_values(TraceTemplate())
    for x in generatedExps:
        assert x <= intVar.maximum and x >= intVar.minimum


def test_intvar4():
    intVar = IntVariable(name=getName(), config=next(CONFIG_GENERATOR))
    generatedExps = intVar.generate_values(TraceTemplate())
    for x in generatedExps:
        assert x <= intVar.maximum and x >= intVar.minimum
