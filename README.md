# DIFFER

DIFFER: Detecting Inconsistencies in Feature or Function Evaluations of Requirements

**Sample Project Configuration**

```yaml
# Sample project configuration file

# Path to the original binary
original: /path/to/binary
# List of recovered binaries to test against
recovered:
  - /path/to/debloated/binary
  - /path/to/another/debloated/binary

# List of traces to run and compare
traces:
  # command line arguments (supports Jinja2 templates from variables)
  - arguments: '{{left}} + {{right}}'

    # Fuzzing variables. The variables are generated and populated into the command line
    # arguments and any template input files for each run.
    variables:
      left:
        type: int
        range:
          minimum: 0
          maximum: 99
          size: 5

      right:
        type: int
        values:
          - -1
          - 0
          - 1

    # List of comparators that verify the debloated version
    comparators:
      # verify stdout matches
      - stdout

      # verify stderr matches a regex pattern
      - id: stderr
        regex: "some_regex_pattern_here"

      # verify the exit code is identical
      - exit_code
```
