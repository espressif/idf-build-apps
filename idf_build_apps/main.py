# SPDX-FileCopyrightText: 2022-2023 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import argparse
import json
import os
import shutil
import sys
import textwrap
import typing as t
from pathlib import (
    Path,
)

from . import (
    CONFIG,
    LOGGER,
)
from .app import (
    App,
    BuildStatus,
)
from .config import (
    get_valid_config,
)
from .constants import (
    ALL_TARGETS,
)
from .finder import (
    _find_apps,
)
from .log import (
    setup_logging,
)
from .utils import (
    BuildError,
    InvalidCommand,
    get_parallel_start_stop,
    to_list,
)


def find_apps(
    paths: t.Union[t.Iterable[str], str],
    target: str,
    *,
    build_system: str = 'cmake',
    recursive: bool = False,
    exclude_list: t.Optional[t.List[str]] = None,
    work_dir: t.Optional[str] = None,
    build_dir: str = 'build',
    config_rules_str: t.Union[t.Iterable[str], str, None] = None,
    build_log_path: t.Optional[str] = None,
    size_json_path: t.Optional[str] = None,
    check_warnings: bool = False,
    preserve: bool = True,
    # settings starts here
    default_build_targets: t.Union[t.Iterable[str], str, None] = None,
    sdkconfig_defaults: t.Optional[str] = None,
    # manifest files ones
    manifest_rootpath: t.Optional[str] = None,
    manifest_files: t.Union[t.Iterable[str], str, None] = None,
    # check app dependency ones
    modified_components: t.Union[t.Iterable[str], str, None] = None,
    modified_files: t.Union[t.Iterable[str], str, None] = None,
    ignore_app_dependencies_filepatterns: t.Union[t.Iterable[str], str, None] = None,
) -> t.List[App]:
    """
    Find app directories in paths (possibly recursively), which contain apps for the given build system, compatible
    with the given target

    :param paths: list of app directories (can be / usually will be a relative path)
    :param target: desired value of IDF_TARGET; apps incompatible with the given target are skipped.
    :param build_system: name of the build system, now only support cmake
    :param recursive: Recursively search into the nested sub-folders if no app is found or not
    :param exclude_list: list of paths to be excluded from the recursive search
    :param work_dir: directory where the app should be copied before building. Support placeholders
    :param build_dir: directory where the build will be done. Support placeholders.
    :param config_rules_str: mapping of sdkconfig file name patterns to configuration names
    :param build_log_path: path of the build log. Support placeholders.
        The logs will go to stdout/stderr if not specified
    :param size_json_path: path of the size.json file. Support placeholders.
        Will not generate size file for each app if not specified
    :param check_warnings: Check for warnings in the build log or not
    :param preserve: Preserve the built binaries or not
    :param manifest_rootpath: The root path of the manifest files. Usually the folders specified in the manifest files
        are relative paths. Use the current directory if not specified
    :param manifest_files: paths of the manifest files
    :param default_build_targets: default build targets used in manifest files
    :param modified_components: modified components
    :param modified_files: modified files
    :param ignore_app_dependencies_filepatterns: file patterns that used for ignoring checking the component
        dependencies
    :param sdkconfig_defaults: semicolon-separated string, pass to idf.py -DSDKCONFIG_DEFAULTS if specified,
        also could be set via environment variables "SDKCONFIG_DEFAULTS"
    :return: list of found apps
    """
    CONFIG.reset_and_config(
        default_build_targets=default_build_targets,
        default_sdkconfig_defaults=sdkconfig_defaults,
        manifest_rootpath=manifest_rootpath,
        manifest_files=manifest_files,
        modified_components=modified_components,
        modified_files=modified_files,
        ignore_app_dependencies_filepatterns=ignore_app_dependencies_filepatterns,
    )

    apps = []
    if target == 'all':
        targets = ALL_TARGETS
    else:
        targets = [target]

    for target in targets:
        for path in to_list(paths):
            apps.extend(
                _find_apps(
                    path,
                    target,
                    build_system=build_system,
                    recursive=recursive,
                    exclude_list=exclude_list or [],
                    work_dir=work_dir,
                    build_dir=build_dir or 'build',
                    config_rules_str=config_rules_str,
                    build_log_path=build_log_path,
                    size_json_path=size_json_path,
                    check_warnings=check_warnings,
                    preserve=preserve,
                )
            )
    apps.sort()

    LOGGER.info('Found %d apps in total', len(apps))
    return apps


def build_apps(
    apps: t.List[App],
    *,
    build_verbose: bool = False,
    parallel_count: int = 1,
    parallel_index: int = 1,
    dry_run: bool = False,
    keep_going: bool = False,
    collect_size_info: t.Optional[str] = None,
    collect_app_info: t.Optional[str] = None,
    ignore_warning_strs: t.Optional[t.List[str]] = None,
    ignore_warning_file: t.Optional[t.List[t.TextIO]] = None,
    copy_sdkconfig: bool = False,
) -> int:
    """
    Build all the specified apps

    :param apps: list of apps to be built
    :param build_verbose: call ``--verbose`` in ``idf.py build`` or not
    :param parallel_count: number of parallel tasks to run
    :param parallel_index: index of the parallel task to run
    :param dry_run: simulate this run or not
    :param keep_going: keep building or not if one app's build failed
    :param collect_size_info: file path to record all generated size files' paths if specified
    :param collect_app_info: file path to record all the built apps' info if specified
    :param ignore_warning_strs: ignore build warnings that matches any of the specified regex patterns
    :param ignore_warning_file: ignore build warnings that matches any of the lines of the regex patterns in the
        specified file
    :param copy_sdkconfig: copy the sdkconfig file to the build directory or not
    :return: exit_code
    :rtype: int
    """
    App.set_ignore_warns_regexes(ignore_warning_strs=ignore_warning_strs, ignore_warning_files=ignore_warning_file)

    start, stop = get_parallel_start_stop(len(apps), parallel_count, parallel_index)
    LOGGER.info('Total %s apps. running build for app %s-%s', len(apps), start, stop)

    exit_code = 0
    LOGGER.info('Building the following apps:')
    if apps[start - 1 : stop]:
        for app in apps[start - 1 : stop]:
            LOGGER.info(app)
    else:
        LOGGER.info('  parallel count is too large. build nothing...')

    # cleanup collect files if exists at this early-stage
    collect_files = []
    for app in apps[start - 1 : stop]:  # we use 1-based
        app.parallel_index = parallel_index
        app.parallel_count = parallel_count

        if collect_app_info:
            app._collect_app_info = collect_app_info

            if app.collect_app_info not in collect_files:
                collect_files.append(app.collect_app_info)

        if collect_size_info:
            app._collect_size_info = collect_size_info

            if app.collect_size_info not in collect_files:
                collect_files.append(app.collect_size_info)

    for f in collect_files:
        if os.path.isfile(f):
            os.remove(f)
            LOGGER.info('=> Remove existing collect file %s', f)
        Path(f).touch()

    for i, app in enumerate(apps):
        index = i + 1  # we use 1-based
        if index < start or index > stop:
            continue

        # attrs
        app.dry_run = dry_run
        app.index = index
        app.verbose = build_verbose

        LOGGER.info('Building app %s: %s', index, repr(app))
        is_built = False
        try:
            is_built = app.build()
        except BuildError as e:
            LOGGER.error(str(e))
            if keep_going:
                exit_code = 1
            else:
                return 1
        finally:
            if app.collect_app_info:
                with open(app.collect_app_info, 'a') as fw:
                    fw.write(app.model_dump_json() + '\n')
                LOGGER.info('=> Recorded app info in %s', app.collect_app_info)

            if is_built:
                if app.collect_size_info and app.size_json_path:
                    try:
                        if not os.path.isfile(app.size_json_path):
                            app.write_size_json()
                    except Exception as e:
                        LOGGER.warning('Adding size info for app %s failed:', app.name)
                        LOGGER.warning(e)
                    else:
                        with open(app.collect_size_info, 'a') as fw:
                            fw.write(
                                json.dumps(
                                    {
                                        'app_name': app.name,
                                        'config_name': app.config_name,
                                        'target': app.target,
                                        'path': app.size_json_path,
                                    }
                                )
                                + '\n'
                            )
                        LOGGER.info('=> Recorded size info file path in %s', app.collect_size_info)

                if copy_sdkconfig:
                    try:
                        shutil.copy(
                            os.path.join(app.work_dir, 'sdkconfig'),
                            os.path.join(app.build_path, 'sdkconfig'),
                        )
                    except Exception as e:
                        LOGGER.warning('Copy sdkconfig file from app %s work dir %s failed:', app.name, app.work_dir)
                        LOGGER.warning(e)
                        pass
                    else:
                        LOGGER.info('=> Copied sdkconfig file from %s to %s', app.work_dir, app.build_path)

            LOGGER.info('')  # add one empty line for separating different builds

    built_apps = [app for app in apps if app.build_status == BuildStatus.SUCCESS]
    if built_apps:
        LOGGER.info('Built the following apps:')
        for app in built_apps:
            LOGGER.info('  %s', app)

    skipped_apps = [app for app in apps if app.build_status == BuildStatus.SKIPPED]
    if skipped_apps:
        LOGGER.info('Skipped the following apps:')
        for app in skipped_apps:
            LOGGER.info('  %s', app)

    failed_apps = [app for app in apps if app.build_status == BuildStatus.FAILED]
    if failed_apps:
        LOGGER.error('Build failed for the following apps:')
        for app in failed_apps:
            LOGGER.error('  %s', app)

    return exit_code


class IdfBuildAppsCliFormatter(argparse.HelpFormatter):
    LINE_SEP = '$LINE_SEP$'

    def _split_lines(self, text, width):
        parts = text.split(self.LINE_SEP)

        text = self._whitespace_matcher.sub(' ', parts[0]).strip()
        return textwrap.wrap(text, width) + parts[1:]

    def _get_help_string(self, action):
        """
        Add the default value to the option help message.

        ArgumentDefaultsHelpFormatter and BooleanOptionalAction when it isn't
        already present. This code will do that, detecting corner cases to
        prevent duplicates or cases where it wouldn't make sense to the end
        user.
        """
        _help = action.help
        if _help is None:
            _help = ''

        if action.dest == 'config_file':
            return _help

        if action.default is not argparse.SUPPRESS:
            if action.default is None:
                default_type = str
            else:
                default_type = type(action.default)

            if action.nargs in [argparse.ZERO_OR_MORE, argparse.ONE_OR_MORE]:
                _type = f'list[{default_type.__name__}]'
            else:
                _type = default_type.__name__

            defaulting_nargs = [argparse.OPTIONAL, argparse.ZERO_OR_MORE]
            if action.option_strings or action.nargs in defaulting_nargs:
                _help += f'{self.LINE_SEP} - default: %(default)s'

            _help += f'{self.LINE_SEP} - config name: {action.dest}'
            _help += f'{self.LINE_SEP} - config type: {_type}'

        return _help


def get_parser():  # type: () -> argparse.ArgumentParser
    parser = argparse.ArgumentParser(
        description='Tools for building ESP-IDF related apps.'
        'Some CLI options can be expanded by the following placeholders, like "--work-dir", "--build-dir", etc.:\n'
        '- @t: would be replaced by the target chip type\n'
        '- @w: would be replaced by the wildcard, usually the sdkconfig\n'
        '- @n: would be replaced by the app name\n'
        '- @f: would be replaced by the escaped app path (replaced "/" to "_")\n'
        '- @i: would be replaced by the build index\n'
        '- @p: would be replaced by the parallel index',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    actions = parser.add_subparsers(dest='action')

    common_args = argparse.ArgumentParser(add_help=False)
    common_args.add_argument(
        '-c',
        '--config-file',
        help='Path to the default configuration file, toml file',
    )

    common_args.add_argument('-p', '--paths', nargs='+', help='One or more paths to look for apps')
    common_args.add_argument('-t', '--target', help='filter apps by given target')
    common_args.add_argument(
        '--build-system', default='cmake', choices=['cmake'], help='filter apps by given build system'
    )
    common_args.add_argument(
        '--recursive',
        action='store_true',
        help='Look for apps in the specified paths recursively',
    )
    common_args.add_argument('--exclude', nargs='+', help='Ignore specified path (if --recursive is given)')
    common_args.add_argument(
        '--work-dir',
        help='If set, the app is first copied into the specified directory, and then built. '
        'If not set, the work directory is the directory of the app. Can expand placeholders',
    )
    common_args.add_argument(
        '--build-dir',
        default='build',
        help='If set, specifies the build directory name. Can be either a name relative to the work directory, '
        'or an absolute path. Can expand placeholders',
    )
    common_args.add_argument(
        '--build-log',
        help='Relative to build dir. The build log will be written to this file instead of sys.stdout if specified. '
        'Can expand placeholders',
    )
    common_args.add_argument(
        '--size-file',
        help='Relative to build dir. The size json will be written to this file if specified. Can expand placeholders',
    )
    common_args.add_argument(
        '--config',
        nargs='+',
        help='Adds configurations (sdkconfig file names) to build. '
        'This can either be FILENAME[=NAME] or FILEPATTERN. FILENAME is the name of the sdkconfig file, '
        'relative to the project directory, to be used. Optional NAME can be specified, '
        'which can be used as a name of this configuration. FILEPATTERN is the name of '
        'the sdkconfig file, relative to the project directory, with at most one wildcard. '
        'The part captured by the wildcard is used as the name of the configuration',
    )
    common_args.add_argument(
        '--sdkconfig-defaults',
        help='semicolon-separated string, pass to idf.py -DSDKCONFIG_DEFAULTS if specified, also could be set via '
        'environment variables "SDKCONFIG_DEFAULTS"',
    )
    common_args.add_argument(
        '-v',
        '--verbose',
        default=0,
        action='count',
        help='Increase the logging level of the whole process. Can be specified multiple times. '
        'By default set to WARNING level. '
        'Specify once to set to INFO level. '
        'Specify twice or more to set to DEBUG level',
    )
    common_args.add_argument(
        '--log-file',
        help='Write the log to the specified file, instead of stderr',
    )
    common_args.add_argument(
        '--check-warnings', action='store_true', help='If set, fail the build if warnings are found'
    )
    common_args.add_argument(
        '--manifest-file',
        nargs='+',
        help='Manifest files which specify the build test rules of the apps',
    )
    common_args.add_argument(
        '--manifest-rootpath',
        help='Root directory for calculating the realpath of the relative path defined in the manifest files. '
        'Would use the current directory if not set',
    )
    common_args.add_argument(
        '--default-build-targets',
        nargs='+',
        help='space-separated list of supported targets. Targets supported in current ESP-IDF branch '
        '(except preview ones) would be used if this option is not set.',
    )
    common_args.add_argument(
        '--modified-components',
        nargs='*',
        default=None,
        help='space-separated list which specifies the modified components. app with `depends_components` set in the '
        'corresponding manifest files would only be built if depends on any of the specified components.',
    )
    common_args.add_argument(
        '--modified-files',
        nargs='*',
        default=None,
        help='space-separated list which specifies the modified files. app with `depends_filepatterns` set in the '
        'corresponding manifest files would only be built if any of the specified file pattern matches any of the '
        'specified modified files.',
    )
    common_args.add_argument(
        '-if',
        '--ignore-app-dependencies-filepatterns',
        nargs='*',
        default=None,
        help='space-separated list which specifies the file patterns used for ignoring checking the app dependencies. '
        'The `depends_components` and `depends_filepatterns` set in the manifest files will be ignored when any of the '
        'specified file patterns matches any of the modified files. Must be used together with --modified-files',
    )

    common_args.add_argument(
        '--no-color',
        action='store_true',
        help='enable colored output by default on UNIX-like systems. enable this flag to make the logs uncolored.',
    )

    find_parser = actions.add_parser('find', parents=[common_args], formatter_class=IdfBuildAppsCliFormatter)
    find_parser.add_argument('-o', '--output', help='Print the found apps to the specified file instead of stdout')

    build_parser = actions.add_parser('build', parents=[common_args], formatter_class=IdfBuildAppsCliFormatter)
    build_parser.add_argument(
        '--build-verbose',
        action='store_true',
        help='Enable verbose output of the build system',
    )
    build_parser.add_argument(
        '--parallel-count',
        default=1,
        type=int,
        help="Number of parallel build jobs. Note that this script doesn't start all jobs simultaneously. "
        'It needs to be executed multiple times with same value of --parallel-count and '
        'different values of --parallel-index',
    )
    build_parser.add_argument(
        '--parallel-index',
        default=1,
        type=int,
        help='Index (1-based) of the job, out of the number specified by --parallel-count',
    )
    build_parser.add_argument(
        '--dry-run',
        action='store_true',
        help="Don't actually build, only print the build commands",
    )
    build_parser.add_argument(
        '--keep-going',
        action='store_true',
        help="Don't exit immediately when a build fails",
    )
    build_parser.add_argument(
        '--no-preserve',
        action='store_true',
        help="Don't preserve the build directory after a successful build",
    )
    build_parser.add_argument(
        '--collect-size-info',
        help='write size info json file while building into the specified file. each line is a json object. '
        'Can expand placeholders',
    )
    build_parser.add_argument(
        '--collect-app-info',
        help='write app info json file while building into the specified file. each line is a json object. '
        'Can expand placeholders',
    )
    build_parser.add_argument(
        '--ignore-warning-str',
        nargs='+',
        help='Ignore the warning string that match the specified regex in the build output',
    )
    build_parser.add_argument(
        '--ignore-warning-file',
        type=argparse.FileType('r'),
        help='Ignore the warning strings in the specified file. Each line should be a regex string',
    )
    build_parser.add_argument(
        '--copy-sdkconfig',
        action='store_true',
        help='Copy the sdkconfig file to the build directory',
    )

    return parser


def validate_args(parser, args):  # type: (argparse.ArgumentParser, argparse.Namespace) -> None
    # validate cli subcommands
    if args.action not in ['find', 'build']:
        parser.print_help()
        raise InvalidCommand('subcommand is required. {find, build}')

    if not args.paths:
        raise InvalidCommand(
            'Must specify at least one path to search for the apps ' 'with CLI option "-p <path>" or "--path <path>"'
        )

    if not args.target:
        raise InvalidCommand(
            'Must specify current build target with CLI option "-t <target>" or "--target <target>". '
            '(choices: [{}]'.format(','.join(ALL_TARGETS + ['all']))
        )

    default_build_targets = []
    if args.default_build_targets:
        for target in args.default_build_targets:
            if target not in ALL_TARGETS:
                raise InvalidCommand(
                    'Unrecognizable target {} specified with "--default-build-targets". '
                    'Current ESP-IDF available targets: {}'.format(target, ALL_TARGETS)
                )

            if target not in default_build_targets:
                default_build_targets.append(target)
    args.default_build_targets = default_build_targets

    if args.ignore_app_dependencies_filepatterns:
        if args.modified_files is None:
            raise InvalidCommand(
                'Must specify "--ignore-component-dependencies-file-patterns" with "--modified-files", '
            )


def apply_config_args(args):  # type: (argparse.Namespace) -> None
    # support toml config file
    config_dict = get_valid_config(custom_path=args.config_file)
    if config_dict:
        for k, v in config_dict.items():
            setattr(args, k, v)

    setup_logging(args.verbose, args.log_file, not args.no_color)


def main():
    parser = get_parser()
    args = parser.parse_args()

    apply_config_args(args)
    validate_args(parser, args)

    # real call starts here
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
        manifest_rootpath=args.manifest_rootpath,
        manifest_files=args.manifest_file,
        default_build_targets=args.default_build_targets,
        modified_components=args.modified_components,
        modified_files=args.modified_files,
        ignore_app_dependencies_filepatterns=args.ignore_app_dependencies_filepatterns,
        sdkconfig_defaults=args.sdkconfig_defaults,
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
    )

    sys.exit(res)
