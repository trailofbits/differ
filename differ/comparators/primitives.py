import re
from pathlib import Path
from subprocess import CompletedProcess
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
          # coerce_bool: false

          # Expect that the exit code be a specific value. This is optional.
          # expect: 0
    """

    def __init__(self, config: dict):
        super().__init__(config)
        self.coerce_bool = config.get('coerce_bool', False)
        expect = config.get('expect')
        if expect is not None:
            self.expect = expect
        else:
            self.expect = None

    def _normalize_exit_code(self, code: int) -> int:
        """
        Normalize the exit code if the ``coerce_bool`` option is enabled. Normalized exit codes are
        either 0 for success or 1 for failure. If ``coerce_bool`` is disabled then this method just
        returns ``code`` unmodified.

        :param code: exit code
        :returns: the normalized exit code
        """
        return code if not self.coerce_bool else int(bool(code))

    def verify_original(self, original: Trace) -> Optional[CrashResult]:
        if self.expect is None:
            return

        # Verify that the original trace exited with the expected exit code
        original_code = self._normalize_exit_code(original.process.returncode)  # type: ignore

        if original_code != self._normalize_exit_code(self.expect):
            return CrashResult(original, f'unexpected exit code: {original.process.returncode}', self)

    def compare(self, original: Trace, debloated: Trace) -> ComparisonResult:
        original_code = self._normalize_exit_code(original.process.returncode)  # type: ignore
        recovered_code = self._normalize_exit_code(debloated.process.returncode)  # type: ignore

        if original_code != recovered_code:
            return ComparisonResult.error(
                self,
                debloated,
                f'exit codes do not match: {original_code} != {recovered_code}',
            )

        return ComparisonResult.success(self, debloated)


class HookScriptComparator(Comparator):
    """
    .. code-block:: yaml

        - id: {comparator_id}
          # Controls how the hook script's exit code is validated and compared. Possible values
          # are:
          #
          #  - true: compare the exit code of the original trace against each debloated trace
          #  - false: do not compare the exit code
          #  - <int>: verify that the exit code is the specified value
          #
          # This is optional with the default being "true" (compare the exit code across traces)
          exit_code: true
    """

    def __init__(self, hook: str, config: dict):
        """
        :param hook: the hook, either 'setup' or 'teardown'
        """
        super().__init__(config)
        self.hook = hook
        self.id = f'{hook}_script'

        self.exit_code = config.get('exit_code', True)

    def get_output(self, trace: Trace) -> tuple[Optional[CompletedProcess], Path]:
        """
        Get the output from the hook script.

        :returns: a tuple containing the completed subprocess and path to the stdout/stderr content
        """
        raise NotImplementedError()  # pragma: no cover

    def verify_original(self, original: Trace) -> Optional[CrashResult]:
        process, _ = self.get_output(original)
        if not isinstance(self.exit_code, bool) and process.returncode != self.exit_code:
            return CrashResult(original, f'unexpected exit code: {process.returncode}', self)

    def compare(self, original: Trace, debloated: Trace) -> ComparisonResult:
        original_process, original_output = self.get_output(original)
        debloated_process, debloated_output = self.get_output(debloated)

        if not original_process or not debloated_process:
            # The hook didn't run, nothing to compare
            return ComparisonResult.success(self, debloated)

        if self.exit_code is not False and original_process.returncode != debloated_process.returncode:
            return ComparisonResult.error(
                self,
                debloated,
                f'{self.hook} hook script exit code does not match: '
                f'original={original_process.returncode}, '
                f'debloated={debloated_process.returncode}',
            )

        if original_output.read_bytes() != debloated_output.read_bytes():
            return ComparisonResult.error(
                self,
                debloated,
                f'{self.hook} hook script output does not match: original={original_output}, '
                f'debloated={debloated_output}',
            )

        return ComparisonResult.success(self, debloated)


@register('setup_script')
class SetupScriptComparator(HookScriptComparator):
    """
    Setup script output comparator. This captures and compares the exit code and stdout/stderr
    content produced by the setup script defined in the template's ``setup`` configuration. See the
    :class:`HookScriptComparator` for available configuration.
    """

    def __init__(self, config: dict):
        super().__init__('setup', config)

    def get_output(self, trace: Trace) -> tuple[Optional[CompletedProcess], Path]:
        return trace.setup_script, trace.setup_script_output


@register('teardown_script')
class TeardownScriptComparator(HookScriptComparator):
    """
    Teardown script output comparator. This captures and compares the exit code and stdout/stderr
    content produced by the teardown script defined in the template's ``teardown`` configuration.
    See the :class:`HookScriptComparator` for available configuration.
    """

    def __init__(self, config: dict):
        super().__init__('teardown', config)

    def get_output(self, trace: Trace) -> tuple[Optional[CompletedProcess], Path]:
        return trace.teardown_script, trace.teardown_script_output


@register('concurrent_script')
class ConcurrentScriptComparator(HookScriptComparator):
    """
    Concurrent script output comparator. This captures and compares the exit code and stdout/stderr
    content produced by the concurrent script defined in the template's ``concurrent``
    configuration. See the :class:`HookScriptComparator` for available configuration.
    """

    def __init__(self, config: dict):
        super().__init__('concurrent', config)

    def get_output(self, trace: Trace) -> tuple[Optional[CompletedProcess], Path]:
        if trace.concurrent_script:
            proc = CompletedProcess(
                trace.concurrent_script.args, trace.concurrent_script.returncode
            )
        else:
            proc = None
        return proc, trace.concurrent_script_output
