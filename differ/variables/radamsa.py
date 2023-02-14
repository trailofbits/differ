import errno
import logging
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from differ.core import FuzzVariable, TraceTemplate

from . import register

RADAMSA_REPO_DIRNAME = (Path(__file__).parents[2] / 'radamsa').absolute()
RADAMSA_BIN_FILENAME = RADAMSA_REPO_DIRNAME / 'bin' / 'radamsa'

logger = logging.getLogger(__name__)


@dataclass
class RadamsaConfig:
    """
    Radamsa variable configuration.
    """

    #: List of initial seed values to fuzz
    seeds: list[str]
    #: Number of values to generate per seed
    count: int = 5

    @classmethod
    def parse(cls, config: dict) -> 'RadamsaConfig':
        """
        Parse a YAML configuration.
        """
        seeds = config['seed']
        if not isinstance(seeds, list):
            seeds = [seeds]

        count = config.get('count', 5)
        return cls([str(item) for item in seeds], count)


@register('radamsa')
class RadamsaVariable(FuzzVariable):
    """
    A variable that uses `Radamsa <https://gitlab.com/akihe/radamsa>`_ to generate test inputs
    from a seed value. Radamsa can be used to trigger bugs within the original and debloated
    binaries on potentially malformed or malicious inputs. This accepts the following configuration
    options:

    .. code-block:: yaml

        - id: radamsa
          # A single seed or a list of seeds to generate values from.
          #
          seed:
            - '/path/to/file'
            - '/a-path/../to/./file_name-with%20space'

          # The number of values to generate per seed. This is optional and the default is 5.
          #
          # count: 5

    Because Radamsa can find new bugs, it is not recommended to expect an exit code for templates
    that have at least one Radamsa variable (see the
    :class:`~differ.comparators.primitives.ExitCodeComparator`).
    """

    def __init__(self, name: str, config: dict):
        super().__init__(name, config)
        self.config = RadamsaConfig.parse(config)

        if not RADAMSA_BIN_FILENAME.is_file():
            raise FileNotFoundError(
                errno.ENOENT, os.strerror(errno.ENOENT), str(RADAMSA_BIN_FILENAME)
            )

    def generate_values(self, template: TraceTemplate) -> Iterator:
        for seed in self.config.seeds:
            yield from self._generate_from_seed(seed, self.config.count)

    def _generate_from_seed(self, seed: str, count: int) -> list[str]:
        if not seed.endswith('\n'):
            seed += '\n'

        proc = subprocess.Popen(
            [str(RADAMSA_BIN_FILENAME), '--count', str(count)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout, _ = proc.communicate(seed.encode())

        # Radamsa is a tiny bit buggy and may return more than `count` values. We unique the
        # returned values and filter out any empty values. For more information, see this comment:
        # https://github.com/trailofbits/differ/issues/15#issuecomment-1428471480
        unique = set(stdout.decode(errors='replace').splitlines(keepends=False))
        items = [item for item in unique if item]
        return items
