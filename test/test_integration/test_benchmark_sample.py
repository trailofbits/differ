import os
from pathlib import Path

from _pytest.python import Metafunc

from differ.core import Project, TraceTemplate
from differ.executor import Executor

REPORT_DIR = Path(__file__).parents[2] / 'integration_test_reports'
PROJECTS_DIR = Path(__file__).parents[2] / 'samples'


def pytest_generate_tests(metafunc: Metafunc):
    from differ.comparators import load_comparators
    from differ.variables import load_variables

    if 'project' not in metafunc.fixturenames:
        return

    app = Executor(REPORT_DIR, overwrite_existing_report=True)
    app.setup()

    params: list[tuple[Executor, Project, TraceTemplate]] = []
    for project_dir in PROJECTS_DIR.iterdir():
        if not project_dir.is_dir():
            continue

        name = project_dir.name.split('-')[0]
        project_filename = project_dir / (name + '.yml')
        if not project_filename.is_file():
            continue

        try:
            project = Project.load(REPORT_DIR, project_filename)
        except:  # noqa: E722
            pass
        else:
            exclude = os.getenv('CI') == 'true_nope' and any(
                template.pcap for template in project.templates
            )
            if not exclude:
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
