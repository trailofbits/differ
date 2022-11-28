# DIFFER

DIFFER: Detecting Inconsistencies in Feature or Function Evaluations of Requirements

**Sample Project Configuration**

```yaml
# Sample project configuration file

# Unique name
name: calculator

# Path to the original binary
original: /path/to/binary
# List of debloated binaries to test against. The key is the debloater name and the value
# is the path to the debloated version of the original binary.
debloaters:
  binrec: /path/to/binrec/binary
  other_debloated: /path/to/other/debloated/binary

# List of templates to generate, run, and compare against the original binary
templates:
  # command line arguments (supports Jinja2 templates from variables)
  - arguments: '{{left}} + {{right}}'

    # Fuzzing variables. The variables are generated and populated into the command line
    # arguments and any template input files for each run.
    variables:
      left:
        type: int
        range:
          # generate 5 integers in the range of 0-99 (inclusive)
          minimum: 0
          maximum: 99
          size: 5

      right:
        type: int
        # Use the following 3 int values
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

<!--
spell-checker:ignore binrec
-->
