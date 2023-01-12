import grp
import hashlib
import pwd
from enum import Enum
from pathlib import Path
from typing import Optional, Union

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


class _FileOwnerComparator:
    """
    Helper class to verify file ownership against a rule set. Accepts the following configuration:

    .. code-block:: yaml

        # Rule for comparing the owning username. This is optional and, by default, the owning user
        # name of the original and debloated file are compared to be matching.
        # user: <name: str, uid: int, true, false>

        # Rule for comparing the owning group. This is optional and, by default, the owning group
        # name of the original and debloated file are compared to be matching.
        # group: <name: str, gid: int, true, false>
    """

    def __init__(self, config: dict):
        self.user: Union[bool, str] = config.get('user', True)
        self.group: Union[bool, str] = config.get('group', True)

        if isinstance(self.user, str):
            self.uid = pwd.getpwnam(self.user).pw_uid
        elif isinstance(self.user, int) and not isinstance(self.user, bool):
            self.uid = self.user
        else:
            self.uid = None

        if isinstance(self.group, str):
            self.gid = grp.getgrnam(self.group).gr_gid
        elif isinstance(self.group, int) and not isinstance(self.group, bool):
            self.gid = self.group
        else:
            self.gid = None

    def verify_file_owner(self, filename: Path) -> bool:
        """
        Verify the file owner based on the configuration.

        :param filename: file to verify
        :returns: ``True`` if the file has the expected ownership, ``False`` otherwise
        """
        stat = filename.lstat()

        if self.uid is not None and stat.st_uid != self.uid:
            return False

        if self.gid is not None and stat.st_gid != self.gid:
            return False

        return True

    def compare_file_owner(self, original_file: Path, debloated_file: Path) -> bool:
        """
        Compare the file owner between the original trace and debloated trace.

        :param original_file: original trace file
        :param debloated_file: debloated trace file
        :returns: ``True`` if the file ownership matches, ``False`` otherwise
        """
        original = original_file.lstat()
        debloated = debloated_file.lstat()

        return (original.st_uid, original.st_gid) == (debloated.st_uid, debloated.st_gid)


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
          #
          # similarity: 100

          # The file must or must not exist. This is optional with the default value being `true`
          # (the file must exist).
          #
          # exists: true

          # The file type, either "file" or "directory". This is optional with the default value
          # being "file" (the path must refer to a normal file).
          #
          # type: file

          # The file mode in octal representation. When specified, the file must have the specified
          # mode. The value can be a string, integer, or variable reference. This is optional with
          # the default value being none.
          #
          # Mode as a string
          # mode: "755"
          #
          # Mode as an integer
          # mode: 755
          #
          # Mode as a variable reference
          # mode:
          #   variable: file_mode

          # The target file to compare against. By default, the file comparator compares a file in
          # the original trace against a file in the debloated trace. The 'target' option changes
          # this behavior and, instead of comparing a file between traces, two files within the
          # same trace are compared. The 'target' is the filename to compare against and must exist
          # within the trace.
          #
          # target: other_file.txt

          # The file owner. This can either be "true" to compare both the owner user and group or
          # it can be a dictionary specifying how to compare the owner user and group. This is
          # optional and, when not specified, no owner information is compared.
          # owner:
          #   # The file owner username. This can be either:
          #   #
          #   #  - true: compare the owner username (default)
          #   #  - false: do not compare the owner username
          #   #  - <str>: expect a specific owner username
          #   #  - <int>: expect a specific owner uid
          #   #
          #   user: root
          #
          #   # The file owner group name. Similar tot the user, his can be either:
          #   #
          #   #  - true: compare the owner group (default)
          #   #  - false: do not compare the owner group
          #   #  - <str>: expect a specific owner group name
          #   #  - <int>: expect a specific owner gid
          #   #
          #   group: sudo
    """

    def __init__(self, config: dict):
        super().__init__(config)
        self.filename: str = config['filename']
        self.exists = config.get('exists', True)
        self.path_type = PathType(config.get('type', 'file'))
        self.target: Optional[str] = config.get('target')
        mode = OctalRef.try_parse(config.get('mode'))
        owner = config.get('owner')

        if isinstance(mode, (int, str)):
            self.mode = int(str(mode), 8)
        elif isinstance(mode, OctalRef):
            self.mode = mode
        else:
            self.mode = MODE_NO_CHECK

        if not self.exists or self.path_type is PathType.directory:
            self.similarity = 0
        else:
            self.similarity = config.get('similarity', 100)

        if owner is True:
            self.owner = _FileOwnerComparator({})
        elif isinstance(owner, dict):
            self.owner = _FileOwnerComparator(owner)
        else:
            self.owner = None

    def verify_original(self, trace: Trace) -> Optional[CrashResult]:
        filename = trace.cwd / self.filename
        if error := self.check_file_type(trace, filename):
            return CrashResult(trace, error, comparator=self)

        if not filename.exists():
            return

        if self.owner and not self.owner.verify_file_owner(filename):
            return CrashResult(trace, 'unexpected file owner', comparator=self)

        if not self.similarity:
            return

        sha1, fuzzy = self.hash_file(filename)

        trace.cache[f'{self.filename}_sha1'] = sha1
        trace.cache[f'{self.filename}_ssdeep'] = fuzzy

        if self.target:
            # Compare two files within the original trace
            similarity = self.compare_file(trace, filename, trace.cwd / self.target)
            if similarity < self.similarity:
                return CrashResult(
                    trace,
                    f'file content does not meet similarity requirement: {self.filename} '
                    f'({similarity}% similar)',
                    comparator=self,
                )

    def check_file_type(self, trace: Trace, filename: Path) -> Optional[str]:
        """
        Verify that the file type, existence, and mode are correct. This method enforces the
        ``type``, ``exists``, and ``mode`` configuration options.

        :param filename: path to the trace file being checked
        :returns: an error message if the check failed or ``None`` if all checks passed
        """
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
        if self.target:
            # compare two files within the debloated trace
            original_filename = debloated.cwd / self.target
        else:
            # compare an original file against a debloated file
            original_filename = original.cwd / self.filename

        if error := self.check_file_type(debloated, filename):
            return ComparisonResult.error(self, debloated, error)

        if not filename.exists():
            return ComparisonResult.success(self, debloated)

        if not original_filename.exists():
            return ComparisonResult.error(
                self, debloated, f'comparison target file does not exist: {original_filename}'
            )

        if self.owner and not self.owner.compare_file_owner(original_filename, filename):
            return ComparisonResult.error(f'{self.id}[owner]', debloated, 'unexpected file owner')

        if not self.similarity:
            return ComparisonResult.success(self, debloated)

        similarity = self.compare_file(original, original_filename, filename)
        if similarity < self.similarity:
            return ComparisonResult.error(
                self,
                debloated,
                f'file content does not meet similarity requirement: {self.filename} '
                f'({similarity}% similar)',
            )
        return ComparisonResult.success(self, debloated)

    def get_file_hashes(self, trace: Trace, filename: Path) -> tuple[str, str]:
        """
        Get the SHA1 and ssdeep hashes for the given file, first checking the trace cache and, if
        the cache doesn't contain an entry for the file, hash the file.

        :param trace: trace to lookup for cached hashes
        :param filename: file to hash
        :returns: a tuple of ``(sha1_hash, ssdeep_hash)``
        """
        if sha1 := trace.cache.get(f'{filename}_sha1'):
            return sha1, trace.cache[f'{filename}_ssdeep']
        return self.hash_file(filename)

    def compare_file(self, trace: Trace, source: Path, target: Path) -> int:
        """
        Compare two files and return their similarity as a whole number percentage.

        :param trace: trace to lookup for cached hashes
        :param source: source filename
        :param target: target filename
        :returns: the similarity between the two files
        """
        source_sha1, source_fuzzy = self.get_file_hashes(trace, source)
        target_sha1, target_fuzzy = self.get_file_hashes(trace, target)

        if source_sha1 == target_sha1:
            similarity = 100
        else:
            similarity = ssdeep.compare(source_fuzzy, target_fuzzy)

        return similarity
