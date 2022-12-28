from invoke import task

# os.environ['PYRIGHT_PYTHON_FORCE_VERSION'] = 'latest'

KWARGS = {'pty': True}


@task
def lint(c):
    c.run('flake8 differ', **KWARGS)
    c.run('isort --check differ', **KWARGS)
    c.run('blue --check differ', **KWARGS)
    c.run('pyright differ', **KWARGS)

    c.run('isort --check test', **KWARGS)
    c.run('blue --check test', **KWARGS)

    c.run('isort --check tasks.py', **KWARGS)
    c.run('blue --check tasks.py', **KWARGS)


@task
def format(c):
    for dirname in ('differ', 'test', 'tasks.py'):
        c.run('blue {}'.format(dirname), **KWARGS)
        c.run('isort {}'.format(dirname), **KWARGS)


@task
def tests(c):
    c.run('coverage run --source=differ -m pytest', **KWARGS)
    c.run('coverage report -m', **KWARGS)


@task
def unit_tests(c):
    c.run('coverage run --source=differ -m pytest -k "not test_project"', **KWARGS)
    c.run('coverage report -m', **KWARGS)


@task
def integration_tests(c):
    c.run('coverage run --source=differ -m pytest -k "test_integration"', **KWARGS)
    c.run('coverage report -m', **KWARGS)


@task
def build_docs(c):
    c.run('sphinx-build -b html docs/source docs/build', **KWARGS)


@task
def spell_check(c):
    patterns = '"differ/**/*" "docs/source/**/*.rst"'
    c.run(
        f'npx cspell lint --show-suggestions --no-progress README.md project.template.yml {patterns}',
        **KWARGS,
    )


@task(lint, spell_check, tests)
def ci(c):
    pass


# @task
# def build(c):
#     c.run('python -m build', **KWARGS)
