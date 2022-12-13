import hashlib
from enum import Enum
from pathlib import Path
from typing import Optional

import ssdeep

from differ.core import Comparator, ComparisonResult, CrashResult, Trace, VariableRef

from . import register


class PathType(Enum):
    file = 'file'
    directory = 'directory'


class OctalRef(VariableRef):
    """
    An octal integer variable reference. This method always returns the octal representation of the
    integer. For example, if a variable has a value of ``555`` (base 10), the value ``365`` is
    returned (``int('555', 8) == 0o555 == 365``).
    """

    def get(self, values: dict) -> int:
        value = values[self.variable]
        return int(str(value), 8)


MODE_NO_CHECK = -1


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
          # algorithm to compare the file content. This option is only honored if the path is a
          # file (`type: file`) and the path must exist (`exists: true`). This is optional with the
          # default value being 100 (files must match exactly).
          # similarity: 100

          # The file must or must not exist. This is optional with the default value being `true`
          # (the file must exist).
          # exists: true

          # The file type, either "file" or "directory". This is optional with the default value
          # being "file" (the path must refer to a normal file).
          # type: file

          # The file mode in octal representation. When specified, the file must have the specified
          # mode. The value can be a string, integer, or variable reference. This is optional with
          # the default value being none.
          # Mode as a string
          # mode: "755"
          #
          # Mode as an integer
          # mode: 755
          #
          # Mode as a variable reference
          # mode:
          #   variable: file_mode
    """

    def __init__(self, config: dict):
        super().__init__(config)
        self.filename: str = config['filename']
        self.exists = config.get('exists', True)
        self.path_type = PathType(config.get('type', 'file'))
        mode = OctalRef.try_parse(config.get('mode'))

        if isinstance(mode, int):
            self.mode = int(str(mode), 8)
        elif isinstance(mode, str) and mode:
            self.mode = int(mode, 8)
        elif isinstance(mode, OctalRef):
            self.mode = mode
        else:
            self.mode = MODE_NO_CHECK

        if not self.exists or self.path_type is PathType.directory:
            self.similarity = 0
        else:
            self.similarity = config.get('similarity', 100)

    def verify_original(self, trace: Trace) -> Optional[CrashResult]:
        filename = trace.cwd / self.filename
        if error := self.check_file_type(trace, filename):
            return CrashResult(trace, error, comparator=self)

        if not self.similarity:
            return

        sha1, fuzzy = self.hash_file(filename)

        trace.cache[f'{self.filename}_sha1'] = sha1
        trace.cache[f'{self.filename}_ssdeep'] = fuzzy

    def check_file_type(self, trace: Trace, filename: Path) -> Optional[str]:
        if self.exists:
            if not filename.exists():
                return f'file does not exist: {self.filename}'

            if self.path_type is PathType.file and not filename.is_file():
                return f'path is not a normal file: {self.filename}'

            if self.path_type is PathType.directory and not filename.is_dir():
                return f'path is not a directory: {self.filename}'
        elif filename.exists():
            return f'file exists: {self.filename}'

        expected_mode = OctalRef.deref(self.mode, trace.context.values)
        if expected_mode != MODE_NO_CHECK and filename.exists():
            mode = filename.stat().st_mode & 0o777
            if expected_mode != mode:
                return (
                    f'file mode does not match expected: mode={mode:o}, expected={expected_mode:o}'
                )

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
        if error := self.check_file_type(debloated, filename):
            return ComparisonResult.error(self, debloated, error)

        if not self.similarity:
            return ComparisonResult.success(self, debloated)

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
