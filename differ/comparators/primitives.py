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
        raise NotImplementedError()  # pragma: no cover

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


class _ExitCodeComparator:
    """
    Helper class to compare process exit codes.
    """

    def __init__(self, config: dict):
        expect = config.get('expect')
        if isinstance(expect, bool):
            # in this case, we need to coerce the exit codes:
            # * true  -> 0 (success)
            # * false -> 1 (failure)
            self.expect = int(not expect)
            self._coerce_bool = True
        else:
            self.expect = expect if isinstance(expect, int) else None
            self._coerce_bool = False

    def _normalize_exit_code(self, code: int) -> int:
        """
        Normalize the exit code if the ``coerce_bool`` option is enabled. Normalized exit codes are
        either 0 for success or 1 for failure. If ``coerce_bool`` is disabled then this method just
        returns ``code`` unmodified.

        :param code: exit code
        :returns: the normalized exit code
        """
        return code if not self._coerce_bool else int(code != 0)

    def compare_exit_code(self, original_code: int, debloated_code: int) -> bool:
        """
        Compare the exit codes.

        :param original_code: the original trace exit code
        :param debloated_code: the debloated trace exit code
        :returns: ``True`` if the exit codes match, ``False`` otherwise
        """
        original_code = self._normalize_exit_code(original_code)
        debloated_code = self._normalize_exit_code(debloated_code)

        return original_code == debloated_code

    def verify_original_exit_code(self, original_code: int) -> bool:
        """
        Verify the process exit code matches the configuration.

        :param original_code: original trace exit code
        :returns: ``True`` if the exit code matches configuration, ``False`` otherwise
        """
        if self.expect is None:
            return True

        normalized = self._normalize_exit_code(original_code)
        return normalized == self.expect


@register('exit_code')
class ExitCodeComparator(Comparator):
    """
    Process exit code comparator. This comparator accepts the following configuration options:

    .. code-block:: yaml

        - id: exit_code
          # Expect that the exit code be a specific value. The value can be any of the following:
          #
          #   - <int>: The exit code must match this integer value exactly.
          #   - false: Allow any non-zero exit code which is treated as a failure in Bash
          #   - true: Only allow an exit code of 0 which is treated as a success in Bash
          #
          # This configuration is optional.
          # expect: 0
    """

    def __init__(self, config: dict):
        super().__init__(config)
        self.comparator = _ExitCodeComparator(config)

    def compare(self, original: Trace, debloated: Trace) -> ComparisonResult:
        if not original.process or not debloated.process:
            # this should not happen
            raise ValueError('original or debloated process has not executed')  # pragma: no cover

        original_code = original.process.returncode
        debloated_code = debloated.process.returncode

        if not self.comparator.compare_exit_code(original_code, debloated_code):
            return ComparisonResult.error(
                self,
                debloated,
                f'exit codes do not match: {original_code} != {debloated}',
            )

        return ComparisonResult.success(self, debloated)

    def verify_original(self, original: Trace) -> Optional[CrashResult]:
        # Verify that the original trace exited with the expected exit code
        if not original.process:
            raise ValueError('original process has not executed')  # pragma: no cover

        exit_code = original.process.returncode
        if not self.comparator.verify_original_exit_code(exit_code):
            return CrashResult(original, f'unexpected exit code: {exit_code}', self)


class HookScriptComparator(Comparator):
    """
    .. code-block:: yaml

        - id: {comparator_id}
          # Controls how the hook script's exit code is validated and compared. Possible values
          # are:
          #
          #  - <dict>: :class:`exit code comparator <ExitCodeComparator>` configuration
          #  - false, null: do not compare the exit code
          #
          # This is optional with the default being enabled with the default exit code comparator
          # configuration.
          #
          # exit_code: {}

          # Controls whether the stdout/stderr content is compared. The default value is true
          # (compare stdout/stderr content) but can be disabled by setting this to false.
          #
          # output: false
    """

    def __init__(self, hook: str, config: dict):
        """
        :param hook: the hook name
        """
        super().__init__(config)
        self.hook = hook
        self.id = f'{hook}_script'

        exit_code_config = config.get('exit_code', {})
        if isinstance(exit_code_config, dict):
            self.exit_code = _ExitCodeComparator(exit_code_config)
        else:
            self.exit_code = None

        self.output = config.get('output', True)

    def get_output(self, trace: Trace) -> tuple[Optional[CompletedProcess], Path]:
        """
        Get the output from the hook script.

        :returns: a tuple containing the completed subprocess and path to the stdout/stderr content
        """
        raise NotImplementedError()  # pragma: no cover

    def verify_original(self, original: Trace) -> Optional[CrashResult]:
        if not self.exit_code:
            return

        process, _ = self.get_output(original)
        if process and not self.exit_code.verify_original_exit_code(process.returncode):
            return CrashResult(
                original, f'unexpected exit code: {process.returncode}', f'{self.id}[exit_code]'
            )

    def compare(self, original: Trace, debloated: Trace) -> ComparisonResult:
        original_proc, original_output = self.get_output(original)
        debloated_proc, debloated_output = self.get_output(debloated)

        if not original_proc or not debloated_proc:
            # The hook didn't run, nothing to compare
            return ComparisonResult.success(self, debloated)

        if self.exit_code and not self.exit_code.compare_exit_code(
            original_proc.returncode, debloated_proc.returncode
        ):
            return ComparisonResult.error(
                f'{self.id}[exit_code]',
                debloated,
                f'{self.hook} hook script exit code does not match: '
                f'original={original_proc.returncode}, '
                f'debloated={debloated_proc.returncode}',
            )

        if self.output and original_output.read_bytes() != debloated_output.read_bytes():
            return ComparisonResult.error(
                f'{self.id}[output]',
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
