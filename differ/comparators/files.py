import hashlib
from pathlib import Path
from typing import Optional

import ssdeep

from differ.core import Comparator, ComparisonResult, CrashResult, Trace

from . import register


@register('file')
class FileComparator(Comparator):
    """
    File content comparator. This comparator accepts a filename in both the original trace and each
    debloated trace. This file is compared and will error if the file content is too dissimilar.
    This comparator accepts the following configuration:

    .. code-block:: yaml

        - id: file
          # The filename, relative to the trace directory to compare.
          filename: program_output.bin
          # The minimum similarity percentage. The comparison will fail if the files are more
          # dissimilar than this threshold. Internally, the comparator uses the ssdeep fuzzy hash
          # algorithm to compare the file content. This is optional with the default value being
          # 100 (files must match exactly).
          # similarity: 100
    """

    def __init__(self, config: dict):
        super().__init__(config)
        self.filename: str = config['filename']
        self.similarity: int = config.get('similarity', 100)

    def verify_original(self, trace: Trace) -> Optional[CrashResult]:
        filename = trace.cwd / self.filename
        if not filename.is_file():
            return CrashResult(trace, f'file does not exist: {self.filename}', comparator=self)

        sha1, fuzzy = self.hash_file(filename)

        trace.cache[f'{self.filename}_sha1'] = sha1
        trace.cache[f'{self.filename}_ssdeep'] = fuzzy

    @classmethod
    def hash_file(cls, filename: Path) -> tuple[str, str]:
        """
        Hash a file using SHA-1 and ssdeep.

        :param filename: path to the file
        :returns: a tuple of ``(sha1_hash, ssdeep_hash)``
        """
        sha1 = hashlib.sha1()
        fuzzy = ssdeep.Hash()
        with filename.open('rb') as file:
            block = file.read(524288)
            while block:
                sha1.update(block)
                fuzzy.update(block)
                block = file.read(524288)

        return sha1.hexdigest(), fuzzy.digest()

    def compare(self, original: Trace, debloated: Trace) -> ComparisonResult:
        filename = debloated.cwd / self.filename
        sha1, fuzzy = self.hash_file(filename)
        if sha1 == original.cache[f'{self.filename}_sha1']:
            similarity = 100
        else:
            similarity = ssdeep.compare(original.cache[f'{self.filename}_ssdeep'], fuzzy)

        if similarity < self.similarity:
            return ComparisonResult.error(
                self,
                debloated,
                f'file content does not meet similarity requirement: {self.filename} '
                f'({similarity}% similar)',
            )
        return ComparisonResult.success(self, debloated)
