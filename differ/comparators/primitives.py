from ..core import Comparator, ComparisonResult, Trace
from . import register


class StringComparator(Comparator):
    """
    Base comparator for performing string comparisons.
    """

    def __init__(self, config: dict):
        super().__init__(config)

    def get_strings(self, trace: Trace) -> tuple[str, bytes, bytes]:
        """
        Get the original and recovered strings to compare against. Subclasses must implement this.

        :return: a tuple containing ``(name, original_str, recovered_str)``
        """
        raise NotImplementedError()

    def compare(self, trace: Trace) -> ComparisonResult:
        name, original, recovered = self.get_strings(trace)

        if original != recovered:
            return ComparisonResult.error(self, f'{name} content does not match')
        return ComparisonResult.matches(self)


@register('stdout')
class StdoutComparator(StringComparator):
    """
    Standard output content comparator.
    """

    def get_strings(self, trace: Trace) -> tuple[str, bytes, bytes]:
        return 'stdout', trace.original.stdout, trace.recovered.stdout


@register('stderr')
class StderrComparator(StringComparator):
    """
    Standard error content comparator.
    """

    def get_strings(self, trace: Trace) -> tuple[str, bytes, bytes]:
        return 'stderr', trace.original.stderr, trace.recovered.stderr


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

    def compare(self, trace: Trace) -> ComparisonResult:
        if self.coerce_bool:
            original_code = bool(trace.original.exit_code)
            recovered_code = bool(trace.recovered.exit_code)
        else:
            original_code = trace.original.exit_code
            recovered_code = trace.original.exit_code

        if original_code != recovered_code:
            return ComparisonResult.error(
                self,
                f'exit codes do not match: {original_code} != {recovered_code}',
            )

        return ComparisonResult.matches(self)
