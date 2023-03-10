# SPDX-FileCopyrightText: 2022-2023 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import argparse
import sys

from .constants import (
    ALL_TARGETS,
)
from .main import (
    build_apps,
    find_apps,
)
from .utils import (
    InvalidCommand,
    setup_logging,
)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Tools for building ESP-IDF related apps.'
        'Some CLI options can be expanded by the following placeholders, like "--work-dir", "--build-dir", etc.:\n'
        '- @t: would be replaced by the target chip type\n'
        '- @w: would be replaced by the wildcard, usually the sdkconfig\n'
        '- @n: would be replaced by the app name\n'
        '- @f: would be replaced by the escaped app path (replaced "/" to "_")\n'
        '- @i: would be replaced by the build index',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    actions = parser.add_subparsers(dest='action')

    common_args = argparse.ArgumentParser(add_help=False)
    common_args.add_argument('-p', '--paths', nargs='+', help='One or more paths to look for apps.')
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
        default=0,
        action='count',
        help='Increase the logging level of the whole process. Can be specified multiple times.',
    )
    common_args.add_argument(
        '--log-file',
        type=argparse.FileType('w'),
        help='Write the script log to the specified file, instead of stderr',
    )
    common_args.add_argument(
        '--check-warnings',
        action='store_true',
        help='Check for warnings in the build output.',
    )
    common_args.add_argument(
        '--manifest-file',
        action='append',
        help='manifest file to specify the build test rules of the apps, could be specified multiple times.',
    )
    common_args.add_argument(
        '--manifest-rootpath',
        help='Root directory for calculating the realpath of the relative path defined in the manifest files. '
        'Would use the current directory if not set.',
    )
    common_args.add_argument(
        '--default-build-targets',
        help='comma-separated target list. IDF supported targets would be used if this option is not set',
    )
    common_args.add_argument(
        '--depends-on-components',
        nargs='*',
        default=None,
        help='space-separated components list, app with `requires_components` set in the corresponding manifest files '
        'would only be built if depends on any of the specified components',
    )
    common_args.add_argument(
        '-if',
        '--ignore-component-dependencies-file-patterns',
        nargs='*',
        default=None,
        help='ignore component dependencies when changed files matches any of the specified file patterns. must used '
        'with --depends-on-files',
    )
    common_args.add_argument(
        '--depends-on-files',
        nargs='*',
        default=None,
        help='space-separated file pattern list, the `requires_components` set in the manifest files will be '
        'ignored when specified files match any of the specified file patterns defined with '
        '--ignore-component-dependencies-file-patterns. Must used with --ignore-component-dependencies-file-patterns',
    )
    common_args.add_argument(
        '--no-color',
        action='store_true',
        help='enable colored output by default on UNIX-like systems. enable this flag to make the logs uncolored.',
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
        help='write size info json file while building into the specified file. each line is a json object.',
    )
    build_parser.add_argument(
        '--collect-app-info',
        type=argparse.FileType('w'),
        help='write app info json file while building into the specified file. each line is a json object.',
    )
    build_parser.add_argument(
        '--ignore-warning-str',
        action='append',
        help='Ignore the warning string that match the specified regex in the build output. '
        'Can be specified multiple times.',
    )
    build_parser.add_argument(
        '--ignore-warning-file',
        type=argparse.FileType('r'),
        help='Ignore the warning strings in the specified file. Each line should be a regex string.',
    )
    build_parser.add_argument(
        '--copy-sdkconfig',
        action='store_true',
        help='Copy the sdkconfig file to the build directory.',
    )

    args = parser.parse_args()
    if args.action not in ['find', 'build']:
        parser.print_help()
        raise InvalidCommand('subcommand is required. {find, build}')

    if not args.paths:
        if args.action == 'find':
            find_parser.print_help()
        elif args.action == 'build':
            build_parser.print_help()

        raise InvalidCommand('Must specify at least one search path with CLI option "-p <path>" or "--path <path>"')

    setup_logging(args.verbose, args.log_file, not args.no_color)

    default_build_targets = []
    if args.default_build_targets:
        for t in args.default_build_targets.split(','):
            t = t.strip()
            if t not in ALL_TARGETS:
                print('Unrecognizable target {}, only know targets {}'.format(t, ALL_TARGETS))
                sys.exit(1)

            if t not in default_build_targets:
                default_build_targets.append(t)

    if (args.ignore_component_dependencies_file_patterns is None) != (args.depends_on_files is None):
        raise InvalidCommand(
            'Must specify "--ignore-component-dependencies-file-patterns" and "--depends-on-files" together'
        )

    apps = find_apps(
        args.paths,
        args.target,
        build_system=args.build_system,
        recursive=args.recursive,
        exclude_list=args.exclude or [],
        work_dir=args.work_dir,
        build_dir=args.build_dir or 'build',
        config_rules_str=args.config,
        build_log_path=args.build_log,
        size_json_path=args.size_file,
        check_warnings=args.check_warnings,
        manifest_files=args.manifest_file,
        default_build_targets=default_build_targets,
        depends_on_components=args.depends_on_components,
        manifest_rootpath=args.manifest_rootpath,
        ignore_component_dependencies_file_patterns=args.ignore_component_dependencies_file_patterns,
        depends_on_files=args.depends_on_files,
    )

    if args.action == 'find':
        if args.output:
            with open(args.output, 'w') as f:
                for app in apps:
                    f.write(str(app) + '\n')
        else:
            print('\n'.join([str(app) for app in apps]))

        sys.exit(0)

    # build from now on
    if args.no_preserve:
        for app in apps:
            app.preserve = False

    res = build_apps(
        apps,
        build_verbose=args.build_verbose,
        parallel_count=args.parallel_count,
        parallel_index=args.parallel_index,
        dry_run=args.dry_run,
        keep_going=args.keep_going,
        collect_size_info=args.collect_size_info,
        collect_app_info=args.collect_app_info,
        ignore_warning_strs=args.ignore_warning_str,
        ignore_warning_file=args.ignore_warning_file,
        copy_sdkconfig=args.copy_sdkconfig,
        depends_on_components=args.depends_on_components,
        manifest_rootpath=args.manifest_rootpath,
        ignore_component_dependencies_file_patterns=args.ignore_component_dependencies_file_patterns,
        depends_on_files=args.depends_on_files,
    )

    if args.depends_on_components is not None:
        sys.exit(res[0])
    else:
        sys.exit(res)
