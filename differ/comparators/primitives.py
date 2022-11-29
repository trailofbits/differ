from ..core import Comparator, ComparisonResult, Trace
from . import register


class StringComparator(Comparator):
    """
    Base comparator for performing string comparisons.
    """

    def __init__(self, config: dict):
        super().__init__(config)

    def get_strings(self, original: Trace, debloated: Trace) -> tuple[str, bytes, bytes]:
        """
        Get the original and recovered strings to compare against. Subclasses must implement this.

        :return: a tuple containing ``(name, original_str, recovered_str)``
        """
        raise NotImplementedError()

    def compare(self, original: Trace, debloated: Trace) -> ComparisonResult:
        name, orig_str, debloated_str = self.get_strings(original, debloated)

        if orig_str != debloated_str:
            return ComparisonResult.error(self, debloated, f'{name} content does not match')
        return ComparisonResult.success(self, debloated)


@register('stdout')
class StdoutComparator(StringComparator):
    """
    Standard output content comparator.
    """

    def get_strings(self, original: Trace, debloated: Trace) -> tuple[str, bytes, bytes]:
        return 'stdout', original.read_stdout(), debloated.read_stdout()


@register('stderr')
class StderrComparator(StringComparator):
    """
    Standard error content comparator.
    """

    def get_strings(self, original: Trace, debloated: Trace) -> tuple[str, bytes, bytes]:
        return 'stderr', original.read_stderr(), debloated.read_stderr()


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
