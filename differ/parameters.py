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
    Generate unique combinations of parameters until all variable values have been exhausted.
    """

    def __init__(self, template: TraceTemplate):
        super().__init__(template)
        self.parameters = [ParameterIterator(template, var) for var in template.variables.values()]
        self.exhausted = False
        self._reversed = list(reversed(self.parameters))

    def generate(self) -> Iterable[dict]:
        exhausted = False
        while not exhausted:
            yield {param.variable.name: param.value for param in self.parameters}

            for param in self._reversed:
                if not param.advance():
                    break
            else:
                exhausted = True
