import re
from typing import Optional

from ..core import Comparator, ComparisonResult, CrashResult, Trace
from . import register


class StringComparator(Comparator):
    """
    Base comparator for performing string comparisons. This comparator accepts the following
    configuration:

    .. code-block:: yaml

        - id: {comparator_id}
          # By default, with no configuration specified, the original and debloated string content
          # is compared and an error is raised if the content does not match exactly.
          #
          # Alternatively, the "pattern" configuration will match the content based on a regex
          # pattern. This uses the Python "re.match" function.
          pattern: '^hello [a-zA-Z][a-zA-Z0-9]*$'
    """

    #: The string field name being compared. Subclasses must set this class attribute.
    STRING_FIELD_NAME = ''

    def __init__(self, config: dict):
        super().__init__(config)
        if pattern := config.get('pattern'):
            self.pattern = re.compile(pattern.encode())
        else:
            self.pattern = None

    def get_string(self, trace: Trace) -> bytes:
        """
        Get the string to compare for a trace. Subclasses must implement this.
        """
        raise NotImplementedError()

    def compare(self, original: Trace, debloated: Trace) -> ComparisonResult:
        orig_str = self.get_string(original)
        debloated_str = self.get_string(debloated)

        if self.pattern:
            if not self.pattern.match(self.get_string(debloated)):
                return ComparisonResult.error(
                    self, debloated, f'{self.STRING_FIELD_NAME} content does not match pattern'
                )
        elif orig_str != debloated_str:
            return ComparisonResult.error(
                self, debloated, f'{self.STRING_FIELD_NAME} content does not match'
            )

        return ComparisonResult.success(self, debloated)

    def verify_original(self, original: Trace) -> Optional[CrashResult]:
        if not self.pattern:
            return None

        string = self.get_string(original)
        if not self.pattern.match(string):
            return CrashResult(
                original,
                f'{self.STRING_FIELD_NAME} content does not match expected pattern',
                comparator=self,
            )

        return None


@register('stdout')
class StdoutComparator(StringComparator):
    """
    Standard output content comparator.
    """

    STRING_FIELD_NAME = 'stdout'

    def get_string(self, trace: Trace) -> bytes:
        return trace.read_stdout()


@register('stderr')
class StderrComparator(StringComparator):
    """
    Standard error content comparator.
    """

    STRING_FIELD_NAME = 'stderr'

    def get_string(self, trace: Trace) -> bytes:
        return trace.read_stderr()


@register('exit_code')
class ExitCodeComparator(Comparator):
    """
    Process exit code comparator. This comparator accepts the following configuration options:

    .. code-block:: yaml

        - id: exit_code
          # Coerce the return value to either True (non-zero) or False (zero) prior to performing
          # the comparison. This is useful when the return value is non-deterministic. This is
          # disabled by default.
          coerce_bool: false
    """

    def __init__(self, config: dict):
        super().__init__(config)
        self.coerce_bool = config.get('coerce_bool', False)

    def compare(self, original: Trace, debloated: Trace) -> ComparisonResult:
        original_code = original.process.returncode  # type: ignore
        recovered_code = debloated.process.returncode  # type: ignore
        if self.coerce_bool:
            original_code = int(bool(original_code))
            recovered_code = int(bool(recovered_code))

        if original_code != recovered_code:
            return ComparisonResult.error(
                self,
                debloated,
                f'exit codes do not match: {original_code} != {recovered_code}',
            )

        return ComparisonResult.success(self, debloated)
