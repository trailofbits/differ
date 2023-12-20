# Contributing to DIFFER

Thanks for your interest in contributing to DIFFER!

This document is primarily focused on detailing DIFFER's high-level development
process. For information on installing and using DIFFER, please refer to the
[README](README.md).

## Issue Tracking

Bugs, new features, enhancements, and general issues are all tracked in our
[GitHub repository](https://github.com/trailofbits/differ).
A GitHub issue should contain all relevant discussion about the topic.
If discussions about a particular issue occur in our slack instance
(empire hacking), please summarize the takeaways from the discussion
in a comment on the issue.

## Development Environment

DIFFER is written in Python 3.9. While we do not prescribe or maintain an
environment a specific IDE / code editor, VScode is a good IDE to start
with for newcomers.

## Code Quality

### Formatting, Linting, and CI

The CI pipeline runs multiple tools that can also be run locally:

- **Formatting**
  - [blue](https://github.com/grantjenks/blue) - code formatting
  - [isort](https://github.com/PyCQA/isort) - import sorting
- **Static Analysis**
  - [pyright](https://github.com/microsoft/pyright) - type checking
  - [flake8](https://github.com/PyCQA/flake8) - static code analysis
- **Unit Tests**
  - [pytest](https://docs.pytest.org) - unit testing
  - [coverage](https://coverage.readthedocs.io) - code coverage
- **Documentation**
  - [sphinx](https://www.sphinx-doc.org/en/master/) - API documentation
- **Spell Checking**
  - [cspell](https://cspell.org/) - Code spell checker.
    - This is a NodeJS package that must be installed, outside of `pipenv`, in a Node v14 or newer environment if you want to run this locally.
      ```bash
      $ npm install -g cspell
      ```

    - The custom dictionary is located in `./cspell-words.txt` and can be updated as needed.

These tools can be run locally using `pipenv`:

```bash
# Run linting checks (static analysis)
$ pipenv run lint

# Format Python code
$ pipenv run format

# Run unit and integration tests
$ pipenv run tests

# Run spell checking (requires cspell)
$ pipenv run spell-check

# Run all CI checks (lint, spell check, test)
$ pipenv run ci
```

## Contributing Code

DIFFER uses the pull request contribution model. When working on an issue,
please create a new branch for your contribution and submit code contributions
via pull request.

### Continuous Integration

Commits to pull requests in progress will be automatically checked to ensure
the code is properly linted and passes unit tests. Before submitting a PR
for review, the contributor shall ensure integration tests pass on their
development machine. Additionally, PR contributors shall add sufficient
unit tests to maintain test coverage.
