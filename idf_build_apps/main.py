# SPDX-FileCopyrightText: 2022-2023 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import argparse
import json
import logging
import os
import re
import shutil
import sys
import textwrap
import typing as t
from pathlib import (
    Path,
)

from . import (
    SESSION_ARGS,
)
from .app import (
    App,
    CMakeApp,
    MakeApp,
)
from .build_apps_args import (
    BuildAppsArgs,
)
from .config import (
    get_valid_config,
)
from .constants import (
    ALL_TARGETS,
    BuildStatus,
)
from .finder import (
    _find_apps,
)
from .junit import (
    TestCase,
    TestReport,
    TestSuite,
)
from .log import (
    setup_logging,
)
from .manifest.manifest import (
    FolderRule,
    Manifest,
)
from .utils import (
    InvalidCommand,
    files_matches_patterns,
    get_parallel_start_stop,
    semicolon_separated_str_to_list,
    to_absolute_path,
    to_list,
)

LOGGER = logging.getLogger(__name__)


def _check_app_dependency(
    manifest_rootpath: t.Optional[str] = None,
    modified_components: t.Optional[t.List[str]] = None,
    modified_files: t.Optional[t.List[str]] = None,
    ignore_app_dependencies_filepatterns: t.Optional[t.List[str]] = None,
) -> bool:
    # not check since modified_components and modified_files are not passed
    if modified_components is None and modified_files is None:
        return False

    # not check since ignore_app_dependencies_filepatterns is passed and matched
    if (
        ignore_app_dependencies_filepatterns
        and modified_files is not None
        and files_matches_patterns(modified_files, ignore_app_dependencies_filepatterns, manifest_rootpath)
    ):
        LOGGER.info(
            'Build all apps since patterns %s matches modified files %s',
            ', '.join(modified_files),
            ', '.join(ignore_app_dependencies_filepatterns),
        )
        return False

    return True


def find_apps(
    paths: t.Union[t.List[str], str],
    target: str,
    *,
    build_system: t.Union[t.Type[App], str] = CMakeApp,
    recursive: bool = False,
    exclude_list: t.Optional[t.List[str]] = None,
    work_dir: t.Optional[str] = None,
    build_dir: str = 'build',
    config_rules_str: t.Optional[t.Union[t.List[str], str]] = None,
    build_log_filename: t.Optional[str] = None,
    size_json_filename: t.Optional[str] = None,
    check_warnings: bool = False,
    preserve: bool = True,
    manifest_rootpath: t.Optional[str] = None,
    manifest_files: t.Optional[t.Union[t.List[str], str]] = None,
    check_manifest_rules: bool = False,
    default_build_targets: t.Optional[t.Union[t.List[str], str]] = None,
    modified_components: t.Optional[t.Union[t.List[str], str]] = None,
    modified_files: t.Optional[t.Union[t.List[str], str]] = None,
    ignore_app_dependencies_filepatterns: t.Optional[t.Union[t.List[str], str]] = None,
    sdkconfig_defaults: t.Optional[str] = None,
    include_skipped_apps: bool = False,
) -> t.List[App]:
    """
    Find app directories in paths (possibly recursively), which contain apps for the given build system, compatible
    with the given target

    :param paths: list of app directories (can be / usually will be a relative path)
    :param target: desired value of IDF_TARGET; apps incompatible with the given target are skipped.
    :param build_system: class of the build system, default CMakeApp
    :param recursive: Recursively search into the nested sub-folders if no app is found or not
    :param exclude_list: list of paths to be excluded from the recursive search
    :param work_dir: directory where the app should be copied before building. Support placeholders
    :param build_dir: directory where the build will be done. Support placeholders.
    :param config_rules_str: mapping of sdkconfig file name patterns to configuration names
    :param build_log_filename: filename of the build log. Will be placed under the app.build_path.
        Support placeholders. The logs will go to stdout/stderr if not specified
    :param size_json_filename: filename to collect the app's size information. Will be placed under the app.build_path.
        Support placeholders. The app's size information won't be collected if not specified
    :param check_warnings: Check for warnings in the build log or not
    :param preserve: Preserve the built binaries or not
    :param manifest_rootpath: The root path of the manifest files. Usually the folders specified in the manifest files
        are relative paths. Use the current directory if not specified
    :param manifest_files: paths of the manifest files
    :param check_manifest_rules: check the manifest rules or not
    :param default_build_targets: default build targets used in manifest files
    :param modified_components: modified components
    :param modified_files: modified files
    :param ignore_app_dependencies_filepatterns: file patterns that used for ignoring checking the component
        dependencies
    :param sdkconfig_defaults: semicolon-separated string, pass to idf.py -DSDKCONFIG_DEFAULTS if specified,
        also could be set via environment variables "SDKCONFIG_DEFAULTS"
    :param include_skipped_apps: include skipped apps or not
    :return: list of found apps
    """
    if default_build_targets:
        default_build_targets = to_list(default_build_targets)
        LOGGER.info('Overriding default build targets to %s', default_build_targets)
        FolderRule.DEFAULT_BUILD_TARGETS = default_build_targets

    if isinstance(build_system, str):
        # backwards compatible
        if build_system == 'cmake':
            build_system = CMakeApp
        elif build_system == 'make':
            build_system = MakeApp
        else:
            raise ValueError('Only Support "make" and "cmake"')
    app_cls = build_system

    # always set the manifest rootpath at the very beginning of find_apps in case ESP-IDF switches the branch.
    Manifest.ROOTPATH = to_absolute_path(manifest_rootpath or os.curdir)
    Manifest.CHECK_MANIFEST_RULES = check_manifest_rules

    if manifest_files:
        rules = set()
        for _manifest_file in to_list(manifest_files):
            LOGGER.debug('Loading manifest file: %s', _manifest_file)
            rules.update(Manifest.from_file(_manifest_file).rules)
        manifest = Manifest(rules)
        App.MANIFEST = manifest

    modified_components = to_list(modified_components)
    modified_files = to_list(modified_files)
    ignore_app_dependencies_filepatterns = to_list(ignore_app_dependencies_filepatterns)
    config_rules_str = to_list(config_rules_str)

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
                    app_cls,
                    recursive,
                    exclude_list or [],
                    work_dir=work_dir,
                    build_dir=build_dir or 'build',
                    config_rules_str=config_rules_str,
                    build_log_filename=build_log_filename,
                    size_json_filename=size_json_filename,
                    check_warnings=check_warnings,
                    preserve=preserve,
                    manifest_rootpath=manifest_rootpath,
                    check_app_dependencies=_check_app_dependency(
                        manifest_rootpath=manifest_rootpath,
                        modified_components=modified_components,
                        modified_files=modified_files,
                        ignore_app_dependencies_filepatterns=ignore_app_dependencies_filepatterns,
                    ),
                    modified_components=modified_components,
                    modified_files=modified_files,
                    sdkconfig_defaults_str=sdkconfig_defaults,
                    include_skipped_apps=include_skipped_apps,
                )
            )

    LOGGER.info(f'Found {len(apps)} apps in total')

    return sorted(apps)


def build_apps(
    apps: t.Union[t.List[App], App],
    *,
    build_verbose: bool = False,
    dry_run: bool = False,
    keep_going: bool = False,
    ignore_warning_strs: t.Optional[t.List[str]] = None,
    ignore_warning_file: t.Optional[t.TextIO] = None,
    copy_sdkconfig: bool = False,
    manifest_rootpath: t.Optional[str] = None,
    modified_components: t.Optional[t.Union[t.List[str], str]] = None,
    modified_files: t.Optional[t.Union[t.List[str], str]] = None,
    ignore_app_dependencies_filepatterns: t.Optional[t.Union[t.List[str], str]] = None,
    check_app_dependencies: t.Optional[bool] = None,
    # BuildAppsArgs
    parallel_count: int = 1,
    parallel_index: int = 1,
    collect_size_info: t.Optional[str] = None,
    collect_app_info: t.Optional[str] = None,
    junitxml: t.Optional[str] = None,
) -> int:
    """
    Build all the specified apps

    :param apps: list of apps to be built
    :param build_verbose: call ``--verbose`` in ``idf.py build`` or not
    :param dry_run: simulate this run or not
    :param keep_going: keep building or not if one app's build failed
    :param ignore_warning_strs: ignore build warnings that matches any of the specified regex patterns
    :param ignore_warning_file: ignore build warnings that matches any of the lines of the regex patterns in the
        specified file
    :param copy_sdkconfig: copy the sdkconfig file to the build directory or not
    :param manifest_rootpath: The root path of the manifest files. Usually the folders specified in the manifest files
        are relative paths. Use the current directory if not specified
    :param modified_components: modified components
    :param modified_files: modified files
    :param ignore_app_dependencies_filepatterns: file patterns that used for ignoring checking the component
        dependencies
    :param check_app_dependencies: check app dependencies or not. if not set, will be calculated by modified_components,
        modified_files, and ignore_app_dependencies_filepatterns
    :param parallel_count: number of parallel tasks to run
    :param parallel_index: index of the parallel task to run
    :param collect_size_info: file path to record all generated size files' paths if specified
    :param collect_app_info: file path to record all the built apps' info if specified
    :param junitxml: path of the junitxml file
    :return: exit code
    """
    apps = to_list(apps)
    modified_components = to_list(modified_components)
    modified_files = to_list(modified_files)
    ignore_app_dependencies_filepatterns = to_list(ignore_app_dependencies_filepatterns)

    test_suite = TestSuite('build_apps')

    ignore_warnings_regexes = []
    if ignore_warning_strs:
        for s in ignore_warning_strs:
            ignore_warnings_regexes.append(re.compile(s))
    if ignore_warning_file:
        for s in ignore_warning_file:
            ignore_warnings_regexes.append(re.compile(s.strip()))
    App.IGNORE_WARNS_REGEXES = ignore_warnings_regexes

    start, stop = get_parallel_start_stop(len(apps), parallel_count, parallel_index)
    LOGGER.info('Total %s apps. running build for app %s-%s', len(apps), start, stop)

    build_apps_args = BuildAppsArgs(
        parallel_count=parallel_count,
        parallel_index=parallel_index,
        collect_size_info=collect_size_info,
        collect_app_info=collect_app_info,
        junitxml=junitxml,
    )
    for app in apps[start - 1 : stop]:  # we use 1-based
        app.build_apps_args = build_apps_args

    # cleanup collect files if exists at this early-stage
    for f in (build_apps_args.collect_app_info, build_apps_args.collect_size_info, build_apps_args.junitxml):
        if f and os.path.isfile(f):
            os.remove(f)
            LOGGER.debug('Remove existing collect file %s', f)
            Path(f).touch()

    exit_code = 0
    for i, app in enumerate(apps):
        index = i + 1  # we use 1-based
        if index < start or index > stop:
            continue

        # attrs
        app.dry_run = dry_run
        app.index = index
        app.verbose = build_verbose

        LOGGER.info('(%s/%s) Building app: %s', index, len(apps), app)

        app.build(
            manifest_rootpath=manifest_rootpath,
            modified_components=modified_components,
            modified_files=modified_files,
            check_app_dependencies=_check_app_dependency(
                manifest_rootpath, modified_components, modified_files, ignore_app_dependencies_filepatterns
            )
            if check_app_dependencies is None
            else check_app_dependencies,
        )
        test_suite.add_test_case(TestCase.from_app(app))

        if app.build_comment:
            LOGGER.info('%s (%s)', app.build_status.value, app.build_comment)
        else:
            LOGGER.info('%s', app.build_status.value)

        if build_apps_args.collect_app_info:
            with open(build_apps_args.collect_app_info, 'a') as fw:
                fw.write(app.to_json() + '\n')
            LOGGER.debug('Recorded app info in %s', build_apps_args.collect_app_info)

        if copy_sdkconfig:
            try:
                shutil.copy(
                    os.path.join(app.work_dir, 'sdkconfig'),
                    os.path.join(app.build_path, 'sdkconfig'),
                )
            except Exception as e:
                LOGGER.warning('Copy sdkconfig file from failed: %s', e)
            else:
                LOGGER.debug('Copied sdkconfig file from %s to %s', app.work_dir, app.build_path)

        if app.build_status == BuildStatus.FAILED:
            if not keep_going:
                return 1
            else:
                exit_code = 1
        elif app.build_status == BuildStatus.SUCCESS:
            if build_apps_args.collect_size_info and app.size_json_path:
                if os.path.isfile(app.size_json_path):
                    with open(build_apps_args.collect_size_info, 'a') as fw:
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
                    LOGGER.debug('Recorded size info file path in %s', build_apps_args.collect_size_info)

        LOGGER.info('')  # add one empty line for separating different builds

    if build_apps_args.junitxml:
        TestReport([test_suite], build_apps_args.junitxml).create_test_report()
        LOGGER.info('Generated junit report for build apps: %s', build_apps_args.junitxml)

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


def get_parser() -> argparse.ArgumentParser:
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
        '--build-system', default='cmake', choices=['cmake', 'make'], help='filter apps by given build system'
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
        '--override-sdkconfig-items',
        nargs='?',
        type=str,
        help='The --override-sdkconfig-items option is a comma-separated list '
        'that permits the overriding of specific configuration items defined '
        'in the SDK\'s sdkconfig file and Kconfig using a command-line argument. '
        'The sdkconfig items specified here override the same sdkconfig '
        'item defined in the --override-sdkconfig-files, if exists.',
    )
    common_args.add_argument(
        '--override-sdkconfig-files',
        nargs='?',
        type=str,
        help='"The --override-sdkconfig-files option is a comma-separated list, '
        'which provides an alternative (alt: --override-sdkconfig-items) '
        'approach for overriding SDK configuration items. '
        'The filepath may be global or relative to the root.',
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
        '--check-manifest-rules',
        action='store_true',
        help='Exit with error if any of the manifest rules does not exist on your filesystem',
    )

    common_args.add_argument(
        '--default-build-targets',
        nargs='+',
        help='space-separated list of supported targets. Targets supported in current ESP-IDF branch '
        '(except preview ones) would be used if this option is not set.',
    )

    common_args.add_argument(
        '--modified-components',
        type=semicolon_separated_str_to_list,
        help='semicolon-separated string which specifies the modified components. '
        'app with `depends_components` set in the corresponding manifest files would only be built '
        'if depends on any of the specified components. '
        'If set to "", the value would be considered as None. '
        'If set to ";", the value would be considered as an empty list',
    )
    common_args.add_argument(
        '--modified-files',
        type=semicolon_separated_str_to_list,
        help='semicolon-separated string which specifies the modified files. '
        'app with `depends_filepatterns` set in the corresponding manifest files would only be built '
        'if any of the specified file pattern matches any of the specified modified files. '
        'If set to "", the value would be considered as None. '
        'If set to ";", the value would be considered as an empty list',
    )
    common_args.add_argument(
        '-if',
        '--ignore-app-dependencies-filepatterns',
        type=semicolon_separated_str_to_list,
        help='semicolon-separated string which specifies the file patterns used for '
        'ignoring checking the app dependencies. '
        'The `depends_components` and `depends_filepatterns` set in the manifest files will be ignored when any of the '
        'specified file patterns matches any of the modified files. '
        'Must be used together with --modified-files. '
        'If set to "", the value would be considered as None. '
        'If set to ";", the value would be considered as an empty list',
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
        'Can expand placeholder @p',
    )
    build_parser.add_argument(
        '--collect-app-info',
        help='write app info json file while building into the specified file. each line is a json object. '
        'Can expand placeholder @p',
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
    build_parser.add_argument(
        '--junitxml',
        help='Path to the junitxml file. If specified, the junitxml file will be generated. Can expand placeholder @p',
    )

    return parser


def validate_args(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
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

    if args.ignore_app_dependencies_filepatterns is not None:
        if args.modified_files is None:
            raise InvalidCommand(
                'Must specify "--ignore-component-dependencies-file-patterns" with "--modified-files", '
            )


def apply_config_args(args: argparse.Namespace) -> None:
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

    SESSION_ARGS.set(args)

    if args.action == 'build':
        args.output = None  # build action doesn't support output option

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
        build_log_filename=args.build_log,
        size_json_filename=args.size_file,
        check_warnings=args.check_warnings,
        manifest_rootpath=args.manifest_rootpath,
        manifest_files=args.manifest_file,
        check_manifest_rules=args.check_manifest_rules,
        default_build_targets=args.default_build_targets,
        modified_components=args.modified_components,
        modified_files=args.modified_files,
        ignore_app_dependencies_filepatterns=args.ignore_app_dependencies_filepatterns,
        sdkconfig_defaults=args.sdkconfig_defaults,
    )

    if args.action == 'find':
        if args.output:
            os.makedirs(os.path.dirname(os.path.realpath(args.output)), exist_ok=True)
            with open(args.output, 'w') as fw:
                for app in apps:
                    fw.write(app.model_dump_json() + '\n')
        else:
            for app in apps:
                print(app)

        sys.exit(0)

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
        manifest_rootpath=args.manifest_rootpath,
        modified_components=args.modified_components,
        modified_files=args.modified_files,
        ignore_app_dependencies_filepatterns=args.ignore_app_dependencies_filepatterns,
        junitxml=args.junitxml,
    )

    built_apps = [app for app in apps if app.build_status == BuildStatus.SUCCESS]
    if built_apps:
        print('Successfully built the following apps:')
        for app in built_apps:
            print(f'  {app}')

    skipped_apps = [app for app in apps if app.build_status == BuildStatus.SKIPPED]
    if skipped_apps:
        print('Skipped building the following apps:')
        for app in skipped_apps:
            print(f'  {app}')

    failed_apps = [app for app in apps if app.build_status == BuildStatus.FAILED]
    if failed_apps:
        print('Failed building the following apps:')
        for app in failed_apps:
            print(f'  {app}')

    sys.exit(res)
