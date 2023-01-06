import re

from differ.core import TraceTemplate
from differ.variables.primitives import StringVariable

"""
You could also add unit tests that exercise the generate_values
function to make sure we honor both self.values and the rexex generation.
"""


def getConfig() -> dict:
    configs = [
        {
            'values': ['random value', 'rv'],
            'regex': {'pattern': 'hello [a-zA-Z0-9]{1,10}', 'count': 3},
        },
        {
            'values': [
                'black',
                'deer',
                'had',
                'receive',
                'hill',
                'lady',
                'one',
                'blow',
                'airplane',
                'give',
                'rod',
                'pure',
                'zero',
                'am',
                'useful',
                'apartment',
                'old',
                'room',
                'cloud',
                'valuable',
                'final',
                'serve',
                'balance',
                'diagram',
                'shine',
                'loud',
                'me',
                'through',
                'dog',
                'circle',
                'slipped',
                'across',
                'tube',
                'occasionally',
                'stopped',
                'swing',
                'bring',
                'every',
                'share',
                'fish',
                'tightly',
                'feel',
            ],
            'regex': {
                'pattern': '//[a-zA-Z0-9]{1,20}//[a-zA-Z0-9]{1,20}//[a-zA-Z0-9]{1,10}',
                'count': 20,
            },
        },
        {'values': [], 'regex': {'pattern': '-[a-zA-Z]{1,7} -[a-zA-Z]{1,4}', 'count': 11}},
        {
            'values': [],
            'regex': {'pattern': '((\\d{3})(?:\\.|-))?(\\d{3})(?:\\.|-)(\\d{4})', 'count': 52},
        },
        {
            'values': ['56', 'dance'],
            'regex': {'pattern': '^\\d+\\.\\d+\\.\\d+\\.\\d+$', 'count': 17},
        },
    ]
    for config in configs:
        yield config


def getName() -> str:
    for x in range(100):
        yield str(x)


CONFIG_GENERATOR = getConfig()


def test_stringvar1():
    strVar = StringVariable(name=getName(), config=next(CONFIG_GENERATOR))
    generatedExps = strVar.generate_values(TraceTemplate())
    for x in generatedExps:
        assert x == 'random value' or x == 'rv' or re.match('hello [a-zA-Z0-9]{1,10}', x)


def test_stringvar2():
    strVar = StringVariable(name=getName(), config=next(CONFIG_GENERATOR))
    generatedExps = strVar.generate_values(TraceTemplate())
    for x in generatedExps:
        assert (
            x == 'black'
            or x == 'deer'
            or x == 'had'
            or x == 'receive'
            or x == 'hill'
            or x == 'lady'
            or x == 'one'
            or x == 'blow'
            or x == 'airplane'
            or x == 'give'
            or x == 'rod'
            or x == 'pure'
            or x == 'zero'
            or x == 'am'
            or x == 'useful'
            or x == 'apartment'
            or x == 'old'
            or x == 'room'
            or x == 'cloud'
            or x == 'valuable'
            or x == 'final'
            or x == 'serve'
            or x == 'balance'
            or x == 'diagram'
            or x == 'shine'
            or x == 'loud'
            or x == 'me'
            or x == 'through'
            or x == 'dog'
            or x == 'circle'
            or x == 'slipped'
            or x == 'across'
            or x == 'tube'
            or x == 'occasionally'
            or x == 'stopped'
            or x == 'swing'
            or x == 'bring'
            or x == 'every'
            or x == 'share'
            or x == 'fish'
            or x == 'tightly'
            or x == 'feel'
            or re.match('//[a-zA-Z0-9]{1,20}//[a-zA-Z0-9]{1,20}//[a-zA-Z0-9]{1,10}', x)
        )


def test_stringvar3():
    strVar = StringVariable(name=getName(), config=next(CONFIG_GENERATOR))
    generatedExps = strVar.generate_values(TraceTemplate())
    for x in generatedExps:
        assert re.match('-[a-zA-Z]{1,7} -[a-zA-Z]{1,4}', x)


def test_stringvar4():
    strVar = StringVariable(name=getName(), config=next(CONFIG_GENERATOR))
    generatedExps = strVar.generate_values(TraceTemplate())
    for x in generatedExps:
        assert re.match('((\\d{3})(?:\\.|-))?(\\d{3})(?:\\.|-)(\\d{4})', x)


def test_stringvar5():
    strVar = StringVariable(name=getName(), config=next(CONFIG_GENERATOR))
    generatedExps = strVar.generate_values(TraceTemplate())
    for x in generatedExps:
        assert x == '56' or x == 'dance' or re.match('^\\d+\\.\\d+\\.\\d+\\.\\d+$', x)
