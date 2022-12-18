import random
from typing import Iterator, Optional

from ..core import FuzzVariable, TraceTemplate
from . import register

import exrex

@register('int')
class IntVariable(FuzzVariable):
    """
    An integer fuzzing variable. This accepts the following configuration options:

    .. code-block:: yaml

        - type: int
          # There are two methods of specifying fuzzing inputs. They can be used together.
          # A specific list of values that must be used:
          values:
            - -1
            - 0
            - 1

          # A range of values (inclusive)
          range:
            # The minimum value
            minimum: 0
            # The maximum value
            maximum: 100
            # The number of samples to generate (default: 5)
            count: 5
    """

    DEFAULT_SAMPLE_COUNT = 5

    def __init__(self, name: str, config: dict):
        super().__init__(name, config)
        range: Optional[dict] = config.get('range')
        self.values: list[int] = config.get('values') or []

        if range:
            self.minimum = range['minimum']
            self.maximum = range['maximum']
            self.count = range.get('count', self.DEFAULT_SAMPLE_COUNT)
        else:
            self.minimum = 0
            self.maximum = 0
            self.count = 0

    def generate_values(self, template: TraceTemplate) -> Iterator[int]:
        if self.values:
            yield from self.values

        if self.count:
            yield from random.sample(range(self.minimum, self.maximum + 1), k=self.count)


@register('str')
class StringVariable(FuzzVariable):
    """
    A string fuzzing variable. This accepts the following configuration options:

    .. code-block:: yaml

        - type: str
          # There are two methods of specifying fuzzing inputs. They can be used together.
          # A specific list of strings that must be used:
          values:
            - 'hello world'

          # A regex pattern to create semi-random/random strings
          regex:
            # The regex pattern
            pattern: 'hello [a-zA-Z0-9]{1,10}'
            # The sample size (default: 5)
            size: 3
    """
    DEFAULT_SAMPLE_SIZE = 5

    def __init__(self, name: str, config: dict):
        super().__init__(name, config)
        self.values: list[int] = config.get('values') or []
        # self.regex: list[int] = config.get('regex') or []
        # self.count = self.regex.get('count', self.DEFAULT_SAMPLE_SIZE)
        if regex := config.get('regex'):
            self.pattern = regex['pattern']
            self.count = regex.get('count', self.DEFAULT_SAMPLE_SIZE)
        else:
            self.pattern = None
            self.count = 0


    def generate_values(self, template: TraceTemplate) -> Iterator[str]:
        if self.values:
            yield from self.values

        if self.pattern:
            yield from [self.generate_string(self.pattern) for _ in range(self.count)]

    def generate_string(self, regex: str) -> str:
        return exrex.getone(regex)
