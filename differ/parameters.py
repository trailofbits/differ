from typing import Iterable

from .core import FuzzVariable, TraceContext, TraceTemplate


class ParameterGenerator:
    """
    Base class for all parameter generators. A parameter generator accepts a trace template and
    produces a unique set of variable values, with each corresponding to a trace context that will
    execute.
    """

    def __init__(self, template: TraceTemplate):
        self.template = template

    def generate(self) -> Iterable[TraceContext]:
        raise NotImplementedError()  # pragma: no cover


class ParameterIterator:
    """
    An iterator over generated variable values where the values are cached and repeated once the
    iterator has been exhausted.
    """

    def __init__(self, template: TraceTemplate, variable: FuzzVariable):
        self.variable = variable
        self._pos = 0
        self._iter = self.variable.generate_values(template)
        self.value = next(self._iter)
        self._cache = [self.value]

    def advance(self) -> bool:
        """
        Advance to the next value and return ``True`` if the iterator has reached the end
        (has been exhausted).
        """
        exhausted = False
        if self._pos:
            try:
                self.value = self._cache[self._pos]
            except IndexError:
                self._pos = 1
                self.value = self._cache[0]
                exhausted = True
            else:
                self._pos += 1
        else:
            try:
                self.value = next(self._iter)
            except StopIteration:
                self._pos = 1
                exhausted = True
                self.value = self._cache[0]
            else:
                self._cache.append(self.value)
        return exhausted


class CombinationParameterGenerator(ParameterGenerator):
    """
    Generate unique combinations of parameters until all variable values and combinations have been
    covered.
    """

    def __init__(self, template: TraceTemplate):
        super().__init__(template)
        self.parameters = [ParameterIterator(template, var) for var in template.variables.values()]
        self.exhausted = False
        self._reversed = list(reversed(self.parameters))

    def generate(self) -> Iterable[dict]:
        """
        Generate all unique combinations. This method works using a waterfall method to cover all
        possible combinations, for example:

        .. code-block:: python

            # trace template variables
            variables = {
                'x': ['a', 'b', 'c'],
                'y': [1, 2, 3],
                'z': [True, False]
            }

            # result from list(generate())
            result = [
                {'x': 'a', 'y': 1, 'z': True  },
                {'x': 'a', 'y': 1, 'z': False },
                {'x': 'a', 'y': 2, 'z': True  },
                {'x': 'a', 'y': 2, 'z': False },
                {'x': 'a', 'y': 3, 'z': True  },
                {'x': 'a', 'y': 3, 'z': False },
                {'x': 'b', 'y': 1, 'z': True  },
                ........
                {'x': 'c', 'y': 3, 'z': True  },
                {'x': 'c', 'y': 3, 'z': False }
            ]
        """
        exhausted = False
        while not exhausted:
            yield {param.variable.name: param.value for param in self.parameters}

            for param in self._reversed:
                if not param.advance():
                    # The iterator has not reached the end, continue
                    break
            else:
                # We are done when every value iterator has been exhausted (all calls to advance()
                # return True).
                exhausted = True
