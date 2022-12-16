from pathlib import Path

from _pytest.python import Metafunc

from differ.core import Project
from differ.executor import Executor

REPORT_DIR = Path(__file__).parents[2] / 'integration_test_reports'
PROJECTS_DIR = Path(__file__).parents[2] / 'samples'


def pytest_generate_tests(metafunc: Metafunc):
    from differ.comparators import load_comparators
    from differ.variables import load_variables

    if 'project' not in metafunc.fixturenames:
        return

    if not REPORT_DIR.exists():
        REPORT_DIR.mkdir()

    load_variables()
    load_comparators()

    projects = []
    for project_dir in PROJECTS_DIR.iterdir():
        if project_dir.is_dir():
            name = project_dir.name.split('-')[0]
            project_filename = project_dir / (name + '.yml')
            if project_filename.is_file():
                try:
                    project = Project.load(REPORT_DIR, project_filename)
                except:  # noqa: E722
                    pass
                else:
                    projects.append(project)

    metafunc.parametrize('project', projects, ids=[project.name for project in projects])


def test_project(project: Project):
    app = Executor(REPORT_DIR, overwrite_existing_report=True)
    app.setup()
    error_count = app.run_project(project)

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
