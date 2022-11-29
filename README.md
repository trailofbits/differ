# DIFFER

DIFFER: Detecting Inconsistencies in Feature or Function Evaluations of Requirements

**Sample Project Configuration**

```yaml
# Sample project configuration file: project.yml

# Unique name
name: coreutils_echo

# Path to the original binary
original: /usr/bin/echo
# List of debloated binaries to test against. The key is the debloater name and the value
# is the path to the debloated version of the original binary.
debloaters:
  # Replace this path to the debloated version
  binrec: /usr/bin/echo

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

      # verify stderr matches
      - id: stderr

      # verify the exit code is identical
      - exit_code
```

To run this project:

```bash
$ pipenv run python -m differ --verbose project.yml
```

The output is stored in the `./reports` directory by default and only errors are recorded. To change the output directory and output all reports, including successful runs:

```bash
$ pipenv run python -m differ --verbose --report-successes --report-dir ./output project.yml
```

Reports are stored in `{report_dir}/{project.name}/report-{engine}-[success|error]-{trace.id}.yml`. For example, a trace of the `binrec` debloater for the `coreutils_echo` project that failed would have a report located at:

```
$ cat ./reports/coreutils_echo/report-binrec-error-001.yml

arguments:
- '70'
- +
- '-1'
binary: /usr/bin/echo-binrec
results:
- comparator: stdout
  details: stdout content does not match
  status: error
- comparator: stderr
  details: ''
  status: success
- comparator: exit_code
  details: ''
  status: success
trace_directory: /home/user/Projects/differ/reports/coreutils_echo/trace-001/binrec
values:
  left: 70
  right: -1
```

In this example, the stdout content did not match the original's.

<!--
spell-checker:ignore binrec coreutils pipenv
-->
