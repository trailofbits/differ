import random
from typing import Iterable, Optional

from ..core import FuzzVariable, Trace
from . import register


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
            # The sample size (default: 5)
            size: 5
    """

    DEFAULT_SAMPLE_SIZE = 5

    def __init__(self, name: str, config: dict):
        super().__init__(name, config)
        range: Optional[dict] = config.get('range')

        self.values = config.get('values') or []
        if range:
            self.minimum = range['minimum']
            self.maximum = range['maximum']
            self.size = range.get('size') or self.DEFAULT_SAMPLE_SIZE
        else:
            self.minimum = 0
            self.maximum = 0
            self.size = 0

    def generate_values(self, trace: Trace) -> Iterable[int]:
        if self.values:
            yield from self.values

        if self.size:
            yield from random.sample(range(self.minimum, self.maximum + 1), k=self.size)
