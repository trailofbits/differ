import warnings
from pathlib import Path

from _pytest.python import Metafunc
from cffi import vengine_cpy

from differ.core import Project, TraceTemplate
from differ.executor import Executor
from differ.util import discover_projects

REPORT_DIR = Path(__file__).parents[2] / 'integration_test_reports'


def pytest_generate_tests(metafunc: Metafunc):
    if 'project' not in metafunc.fixturenames:
        return

    # cffi/vengine_cpy.py will import the 'imp' module which triggers the following warning. We
    # don't want pytest to ignore this warning so that we don't confuse the user or CI.
    # warnings.filterwarnings(
    #     'ignore', category=DeprecationWarning, message='the imp module is deprecated'
    # )

    app = Executor(REPORT_DIR, overwrite_existing_report=True)
    app.setup()

    params: list[tuple[Executor, Project, TraceTemplate]] = []
    for project in discover_projects(report_dir=REPORT_DIR):
        # The following check is disabled which makes it so pcap templates are not run in CI.
        # This appears to be working but, if these samples become flaky or begin breaking, we
        # should disable them again.
        #
        # exclude = os.getenv('CI') == 'true' and any(
        #     template.pcap for template in project.templates
        # )
        # if not exclude:
        app.setup_project(project)
        params.extend((app, project, template) for template in project.templates)

    metafunc.parametrize(
        'app,project,template',
        params,
        ids=[f'{project.name}_{template.id}' for _, project, template in params],
    )


def test_benchmark_sample(app: Executor, project: Project, template: TraceTemplate):
    # error_count = app.run_project(project)
    _, error_count = app.run_template(project, template)

    if error_count:
        for filename in project.directory.iterdir():
            if filename.name.startswith('report-') and filename.is_file():
                print('# Error report:', filename.name)
                print(filename.read_text())
                print('----------')

    assert error_count == 0, (
        f'Project {project.name} failed with {error_count} errors; see report directory for '
        f'details: {project.directory}'
    )
