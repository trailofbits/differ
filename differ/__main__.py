if __name__ == '__main__':
    import argparse
    from pathlib import Path

    from .core import Project
    from .executor import Executor

    parser = argparse.ArgumentParser('differ')
    parser.add_argument('-v', '--verbose', action='store_true', help='verbose log output')
    parser.add_argument(
        '-s',
        '--report-successes',
        action='store_true',
        help='write a report for both successful and failed traces',
    )
    parser.add_argument(
        '-r',
        '--report-dir',
        action='store',
        default='./reports',
        help='report directory where traces are executed from and reports are stored',
    )
    parser.add_argument(
        '-m',
        '--max-permutations',
        action='store',
        default=100,
        type=int,
        help='maximum number of variable permutations to run per template',
    )
    parser.add_argument('-f', '--force', action='store_true', help='overwrite existing reports')
    parser.add_argument('project_filename', help='project YAML file to run')

    args = parser.parse_args()
    app = Executor(
        Path(args.report_dir),
        report_successes=args.report_successes,
        max_permutations=args.max_permutations,
        verbose=args.verbose,
        overwrite_existing_report=args.force,
    )
    app.setup()

    project = Project.load(app.root, args.project_filename)
    app.run_project(project)
