# SPDX-FileCopyrightText: 2022 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import argparse
import sys

from . import LOGGER
from .app import App
from .finder import find_apps
from .manifest.manifest import Manifest
from .utils import setup_logging, get_parallel_start_stop, BuildError


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Tools for building ESP-IDF related apps.'
        'Some CLI options can be expanded by the following placeholders, like "--work-dir", "--build-dir", etc.:'
        '- @t: would be replaced by the target chip type'
        '- @w: would be replaced by the wildcard, usually the sdkconfig'
        '- @n: would be replaced by the app name'
        '- @f: would be replaced by the escaped app path (replaced "/" to "_")'
        '- @i: would be replaced by the build index'
    )
    actions = parser.add_subparsers(dest='action')

    common_args = argparse.ArgumentParser(add_help=False)
    common_args.add_argument(
        '-p', '--paths', nargs='+', help='One or more paths to look for apps.'
    )
    common_args.add_argument('-t', '--target', help='filter apps by given target.')
    common_args.add_argument(
        '--build-system',
        default='cmake',
        choices=['cmake'],
        help='build with given build system',
    )
    common_args.add_argument(
        '--recursive',
        action='store_true',
        help='Look for apps in the specified directories recursively.',
    )
    common_args.add_argument(
        '--exclude',
        action='append',
        help='Ignore specified directory (if --recursive is given). Can be used multiple times.',
    )
    common_args.add_argument(
        '--work-dir',
        help='If set, the app is first copied into the specified directory, and then built. '
        'If not set, the work directory is the directory of the app. Can expand placeholders.',
    )
    common_args.add_argument(
        '--build-dir',
        help='If set, specifies the build directory name. Can expand placeholders. Can be either a '
        'name relative to the work directory, or an absolute path.',
    )
    common_args.add_argument(
        '--build-log',
        help='If specified, the build log will be written to this file. Can expand placeholders.',
    )
    common_args.add_argument(
        '--size-file',
        help='the size json will be written to this file. Can expand placeholders.',
    )
    common_args.add_argument(
        '--config',
        action='append',
        help='Adds configurations (sdkconfig file names) to build. Could be specified for multiple times.'
        'This can either be '
        'FILENAME[=NAME] or FILEPATTERN. FILENAME is the name of the sdkconfig file, '
        'relative to the project directory, to be used. Optional NAME can be specified, '
        'which can be used as a name of this configuration. FILEPATTERN is the name of '
        'the sdkconfig file, relative to the project directory, with at most one wildcard. '
        'The part captured by the wildcard is used as the name of the configuration.',
    )
    common_args.add_argument(
        '-v',
        '--verbose',
        action='count',
        help='Increase the logging level of the whole process. Can be specified multiple times.',
    )
    common_args.add_argument(
        '--log-file',
        type=argparse.FileType('w'),
        help='Write the script log to the specified file, instead of stderr',
    )
    common_args.add_argument(
        '--manifest-file',
        action='append',
        help='manifest file to specify the build test rules of the apps, could be specified multiple times.',
    )

    find_parser = actions.add_parser('find', parents=[common_args])
    find_parser.add_argument(
        '-o',
        '--output',
        help='Output the found apps to the specified file instead of sys.stdout.',
    )

    build_parser = actions.add_parser('build', parents=[common_args])
    build_parser.add_argument(
        '--build-verbose',
        action='store_true',
        help='Enable verbose output from build system.',
    )
    build_parser.add_argument(
        '--parallel-count',
        default=1,
        type=int,
        help="Number of parallel build jobs. Note that this script doesn't start the jobs, "
        + 'it needs to be executed multiple times with same value of --parallel-count and '
        + 'different values of --parallel-index.',
    )
    build_parser.add_argument(
        '--parallel-index',
        default=1,
        type=int,
        help='Index (1-based) of the job, out of the number specified by --parallel-count.',
    )
    build_parser.add_argument(
        '--dry-run',
        action='store_true',
        help="Don't actually build, only print the build commands",
    )
    build_parser.add_argument(
        '--keep-going',
        action='store_true',
        help="Don't exit immediately when a build fails.",
    )
    build_parser.add_argument(
        '--no-preserve',
        action='store_true',
        help="Don't preserve the build directory after a successful build.",
    )
    build_parser.add_argument(
        '--collect-size-info',
        type=argparse.FileType('w'),
        help='write size info json file while building, record the file location into the specified file',
    )
    args = parser.parse_args()
    setup_logging(args.verbose, args.log_file)

    if args.manifest_file:
        rules = set()
        for _manifest_file in args.manifest_file:
            LOGGER.info('Loading manifest file: %s', _manifest_file)
            rules.update(Manifest.from_file(_manifest_file).rules)
        manifest = Manifest(rules)
        App.MANIFEST = manifest

    apps = []
    for path in args.paths:
        apps.extend(
            find_apps(
                path,
                args.target,
                args.build_system,
                args.recursive,
                args.exclude or [],
                args.work_dir,
                args.build_dir or 'build',
                args.build_log,
                args.size_file,
                args.config,
            )
        )
    apps.sort()

    if args.action == 'find':
        LOGGER.info('Found %d apps:', len(apps))
        if args.output:
            with open(args.output, 'w') as f:
                for app in apps:
                    f.write(str(app) + '\n')
        else:
            print('\n'.join([str(app) for app in apps]))

        sys.exit(0)

    # build from now on
    start, stop = get_parallel_start_stop(
        len(apps), args.parallel_count, args.parallel_index
    )
    LOGGER.info(
        'Total %s apps. running build for app %s-%s', len(apps), start + 1, stop
    )

    failed_apps = []
    for i, app in enumerate(apps):
        if i < start or i >= stop:
            continue

        # attrs
        app.dry_run = args.dry_run
        app.index = i
        app.preserve = not args.no_preserve
        app.verbose = args.build_verbose

        LOGGER.debug('=> Building app %s: %s', i, repr(app))
        try:
            app.build()
            if args.collect_size_info:
                app.collect_size_json(args.collect_size_info)
        except BuildError as e:
            LOGGER.error(str(e))
            if args.keep_going:
                failed_apps.append(app)
            else:
                raise SystemExit(1)
