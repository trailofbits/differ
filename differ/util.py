from pathlib import Path

from .core import Project

SAMPLE_DIR = Path(__file__).parents[1] / 'samples'
REPORT_DIR = Path(__file__).parents[1] / 'reports'


def discover_projects(
    projects_dir: Path = SAMPLE_DIR, report_dir: Path = REPORT_DIR
) -> list[Project]:
    """
    Load projects from a directory. This method only looks 1 level deep for project files, so the
    directory structure must look like the following:::

        project_1/
            project.yml
            other_files

        project_2/
            another_project.yml
            other_files_2

    :param project_dir: the directory to load projects from
    :param report_dir: the output report directory
    :returns: the list of loaded projects
    """
    projects = []
    for project_dir in projects_dir.iterdir():
        if not project_dir.is_dir():
            continue

        potential_project_files = []
        for filename in project_dir.iterdir():
            if filename.is_file() and filename.suffix in ('.yml', '.yaml'):
                potential_project_files.append(filename)

        for project_filename in potential_project_files:
            try:
                project = Project.load(report_dir, project_filename)
            except:  # noqa: E722
                pass
            else:
                projects.append(project)

    return sorted(projects, key=lambda item: item.name)
