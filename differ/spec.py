from pathlib import Path

from .core import Project
from .util import REPORT_DIR, discover_projects

if __name__ == '__main__':
    import argparse
    import csv
    import sys

    from .comparators import load_comparators
    from .variables import load_variables

    load_comparators()
    load_variables()

    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-p',
        '--project',
        action='append',
        type=Path,
        help='get the spec for one or more project files',
    )
    parser.add_argument(
        '-o', '--output', action='store', type=Path, help='write to specified file'
    )

    args = parser.parse_args()
    if args.project:
        projects = [Project.load(REPORT_DIR, filename) for filename in args.project]
    else:
        projects = discover_projects()

    if args.output:
        file = args.output.open('w', newline='')
    else:
        file = sys.stdout

    writer = csv.writer(file)
    writer.writerow(('binary', 'version', 'name', 'arguments', 'stdin', 'summary'))
    for project in projects:
        for template in project.templates:
            stdin = 'yes' if template.stdin else 'no'
            writer.writerow(
                (
                    project.name,
                    project.version,
                    template.name,
                    template.arguments,
                    stdin,
                    template.summary,
                )
            )

    if args.output:
        file.close()
