# DIFFER

![](https://github.com/trailofbits/differ/actions/workflows/ci.yml/badge.svg)

DIFFER: Detecting Inconsistencies in Feature or Function Evaluations of Requirements

## Overview
Program transformation tools (like software debloating tools) often neglect the need for
post-transfomation validation of the modified programs they create, opting to leave this entirely
to the user. Existing approaches like regression and fuzz testing do not naturally support testing
transformed programs against their original versions.

DIFFER is a novel differential testing tool for transformed programs that combines elements from
differential, regression, and fuzz testing approaches. DIFFER allows users to specify seed inputs
that correspond to both unmodified and modified program behaviors/features. It runs the original
program and one or more of its transformed variants with these inputs and compares their outputs.

DIFFER expects that inputs for unmodified features will result in outputs that are the same for the
original and transformed programs. Conversely, it expects inputs for modified features to cause the
original and transformed programs to produce differing outputs. If DIFFER detects unexpected
matches, differences or crashes it reports them to the user to inspect. DIFFER's reports can help
the user identify mistakes in the transformation tool or its configuration

As is the case with all dynamic analysis tools, it is possible that DIFFER reports may be false
positives. To reduce false positive rates to a minimum, DIFFER allows users to define custom output
comparators that can account for expected differences in outputs (e.g., a program timestamps its
console output). Additionally, DIFFER supports template-based mutational fuzzing of seed inputs to
ensure maximum coverage of the input space (i.e., avoid false negatives) for both unmodified and
modified features.

It is important to note that DIFFER does not and cannot provide formal guarantees of soundness
in transformation tools or the modified programs they produce. Like other dynamic analysis testing
approaches, DIFFER cannot exhaustively test the input space for complex programs in the general
case.

## Debloating Use Case

DIFFER was originally designed to help validate debloated programs created by software debloaters.
This work is currently published for reference at the link below. We welcome contributions to this
DIFFER and hope you find it useful in your research / security work. If you use this tool in
your research, please cite the following paper:

**Brown, Michael D., et al. "SoK: A Broad Comparative Evaluation of Software Debloating Tools". arXiv CS.SE. 2023.**[\[pdf\]](https://arxiv.org/abs/2312.13274)


## Setup

### Installing Dependencies

1. Install Python 3.9 and dependencies. For Ubuntu 20.04, the [deadsnakes PPA](https://launchpad.net/~deadsnakes/+archive/ubuntu/ppa) can be used:
   ```bash
   $ sudo add-apt-repository ppa:deadsnakes/ppa
   $ sudo apt update
   $ sudo apt-get install python3.9 python3.9-dev python3-pip python3.9-venv libfuzzy-dev lftp lighttpd memcached \
       tcpdump binutils unzip poppler-utils imagemagick nmap
   $ sudo systemctl stop memcached
   $ sudo systemctl disable memcached
   ```
2. Install `pipenv`, which manages the virtual environment.
   ```bash
   $ python3.9 -m pip install --user pipenv
   ```
3. Create the virtual environment and install development dependencies:
   ```bash
   $ pipenv sync --dev
   ```
4. Clone and build Radamsa.
   ```bash
   $ ./setup-radamsa.sh
   ```
5. Install [Node.js](https://nodejs.org/en/), which is required by the type checker (pyright). On Linux, use the [node version manager](https://github.com/nvm-sh/nvm) and on Windows install Node.js 18+ and add `node.exe` to the `PATH`.

### Allow current user to execute tcpdump

The current user will need to be able to run `tcpdump` without `sudo` in order for the packet capture functionality to work properly. This is not necessary if DIFFER is being run as `root`.

1. Enable the network traffic capture capabilities for the `tcpdump` binary.
   ```bash
   $ sudo setcap cap_net_raw,cap_net_admin=eip /usr/sbin/tcpdump
   ```

2. Verify that you can run `tcpdump` without sudo. The following command should work properly and produce a pcap file.
   ```bash
   $ tcpdump -i lo -w test.pcap
   # wait a few seconds
   # ctrl+c

   $ ls -l test.pcap
   # verify that the file exists and is not empty
   ```

## Running Differ

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
          count: 5

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
$ pipenv run differ --verbose project.yml
```

The output is stored in the `./reports` directory by default and only errors are recorded. To change the output directory and output all reports, including successful runs:

```bash
$ pipenv run differ --verbose --report-successes --report-dir ./output project.yml
```

Reports are stored in `{report_dir}/{project.name}/report-{engine}-[success|error]-{trace.id}.yml`. For example, a trace of the `binrec` debloater for the `coreutils_echo` project that failed would have a report located at:

```yaml
# $ cat ./reports/coreutils_echo/report-binrec-error-001.yml

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

## Getting Benchmark Sample Specs

The `differ.spec` module loads all benchmark sample projects and outputs a CSV report containing all the command line argument invocations that will be executed. This is useful when determining what features are expected to be present in debloated samples.

```bash
$ pipenv run python differ-spec -o specs.csv
```

## Acknowledgements

This material is based upon work supported by the Office of Naval
Research (ONR) under Contract No. N00014-21-C-1032. Any opinions, findings
and conclusions or recommendations expressed in this material are those
of the author(s) and do not necessarily reflect the views of the ONR.

<!--
spell-checker:ignore binrec coreutils pipenv deadsnakes pyright venv isort pytest libfuzzy lftp lighttpd chgrp setcap usermod binutils poppler imagemagick
-->
