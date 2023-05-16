# SPDX-FileCopyrightText: 2022-2023 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import argparse
import io
import json
import os
import re
import shutil
import sys
import textwrap
import warnings
from pathlib import (
    Path,
)

from . import (
    LOGGER,
)
from .app import (
    App,
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
from .manifest.manifest import (
    FolderRule,
    Manifest,
)
from .utils import (
    BuildError,
    InvalidCommand,
    files_matches_patterns,
    get_parallel_start_stop,
    to_absolute_path,
    to_list,
)

try:
    import typing as t
except ImportError:
    pass


def _check_components_dependency(
    manifest_rootpath,  # type: str
    modified_components,  # type: list[str] | None
    modified_files,  # type: list[str] | None
    ignore_component_dependencies_file_patterns,  # type: list[str] | None
):  # type: (...) -> bool
    # not check since `--modified-components` is not passed
    if modified_components is None and modified_files is None:
        return False

    # not check since `--ignore-component-dependency-file-pattern` is passed and matched
    if (
        ignore_component_dependencies_file_patterns
        and modified_files
        and files_matches_patterns(modified_files, ignore_component_dependencies_file_patterns, manifest_rootpath)
    ):
        LOGGER.debug(
            'Skipping check component dependencies for apps since files %s matches patterns: %s',
            ', '.join(modified_files),
            ', '.join(ignore_component_dependencies_file_patterns),
        )
        return False

    return True


def find_apps(
    paths,  # type: list[str] | str
    target,  # type: str
    build_system='cmake',  # type: str
    recursive=False,  # type: bool
    exclude_list=None,  # type: list[str] | None
    work_dir=None,  # type: str | None
    build_dir='build',  # type: str
    config_rules_str=None,  # type: list[str] | str | None
    build_log_path=None,  # type: str | None
    size_json_path=None,  # type: str | None
    check_warnings=False,  # type: bool
    preserve=True,  # type: bool
    manifest_rootpath=None,  # type: str | None
    manifest_files=None,  # type: list[str] | str | None
    default_build_targets=None,  # type: list[str] | str | None
    modified_components=None,  # type: list[str] | str | None
    modified_files=None,  # type: list[str] | str | None
    ignore_component_dependencies_file_patterns=None,  # type: list[str] | str | None
    sdkconfig_defaults=None,  # type: str | None
):  # type: (...) -> list[App]
    """
    Find app directories in paths (possibly recursively), which contain apps for the given build system, compatible
    with the given target

    :param paths: list of app directories (can be / usually will be a relative path)
    :type paths: list[str] | str
    :param target: desired value of IDF_TARGET; apps incompatible with the given target are skipped.
    :type target: str
    :param build_system: name of the build system, now only support cmake
    :type build_system: str
    :param recursive: Recursively search into the nested sub-folders if no app is found or not
    :type recursive: bool
    :param exclude_list: list of paths to be excluded from the recursive search
    :type exclude_list: list[str] | None
    :param work_dir: directory where the app should be copied before building. Support placeholders
    :type work_dir: str | None
    :param build_dir: directory where the build will be done. Support placeholders.
    :type build_dir: str
    :param config_rules_str: mapping of sdkconfig file name patterns to configuration names
    :type config_rules_str: list[str] | str | None
    :param build_log_path: path of the build log. Support placeholders.
        The logs will go to stdout/stderr if not specified
    :type build_log_path: str | None
    :param size_json_path: path of the size.json file. Support placeholders.
        Will not generate size file for each app if not specified
    :type size_json_path: str | None
    :param check_warnings: Check for warnings in the build log or not
    :type check_warnings: bool
    :param preserve: Preserve the built binaries or not
    :type preserve: bool
    :param manifest_rootpath: The root path of the manifest files. Usually the folders specified in the manifest files
        are relative paths. Use the current directory if not specified
    :type manifest_rootpath: str | None
    :param manifest_files: paths of the manifest files
    :type manifest_files: list[str] | str | None
    :param default_build_targets: default build targets used in manifest files
    :type default_build_targets: list[str] | str | None
    :param modified_components: modified components
    :type modified_components: list[str] | str | None
    :param modified_files: modified files
    :type modified_files: list[str] | str | None
    :param ignore_component_dependencies_file_patterns: file patterns that used for ignoring checking the component
        dependencies
    :type ignore_component_dependencies_file_patterns: list[str] | str | None
    :param sdkconfig_defaults: semicolon-separated string, pass to idf.py -DSDKCONFIG_DEFAULTS if specified,
        also could be set via environment variables "SDKCONFIG_DEFAULTS"
    :type sdkconfig_defaults: str | None
    :return: list of found apps
    :rtype: list[App]
    """
    if default_build_targets:
        default_build_targets = to_list(default_build_targets)
        LOGGER.info('Overriding DEFAULT_BUILD_TARGETS to %s', default_build_targets)
        FolderRule.DEFAULT_BUILD_TARGETS = default_build_targets

    # always set the manifest rootpath at the very beginning of find_apps in case ESP-IDF switches the branch.
    Manifest.ROOTPATH = to_absolute_path(manifest_rootpath or os.curdir)

    if manifest_files:
        rules = set()
        for _manifest_file in to_list(manifest_files):
            LOGGER.debug('Loading manifest file: %s', _manifest_file)
            rules.update(Manifest.from_file(_manifest_file).rules)
        manifest = Manifest(rules)
        App.MANIFEST = manifest

    modified_components = to_list(modified_components)
    modified_files = to_list(modified_files)
    ignore_component_dependencies_file_patterns = to_list(ignore_component_dependencies_file_patterns)

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
                    build_system,
                    recursive,
                    exclude_list or [],
                    work_dir=work_dir,
                    build_dir=build_dir or 'build',
                    config_rules_str=config_rules_str,
                    build_log_path=build_log_path,
                    size_json_path=size_json_path,
                    check_warnings=check_warnings,
                    preserve=preserve,
                    manifest_rootpath=manifest_rootpath,
                    modified_components=modified_components,
                    modified_files=modified_files,
                    check_component_dependencies=_check_components_dependency(
                        manifest_rootpath,
                        modified_components,
                        modified_files,
                        ignore_component_dependencies_file_patterns,
                    ),
                    sdkconfig_defaults_str=sdkconfig_defaults,
                )
            )
    apps.sort()

    LOGGER.info('Found %d apps in total', len(apps))
    return apps


def build_apps(
    apps,  # type: list[App] | App
    build_verbose=False,  # type: bool
    parallel_count=1,  # type: int
    parallel_index=1,  # type: int
    dry_run=False,  # type: bool
    keep_going=False,  # type: bool
    collect_size_info=None,  # type: str | t.TextIO | None
    collect_app_info=None,  # type: str | t.TextIO | None
    ignore_warning_strs=None,  # type: list[str] | None
    ignore_warning_file=None,  # type: t.TextIO | None
    copy_sdkconfig=False,  # type: bool
    manifest_rootpath=None,  # type: str | None
    modified_components=None,  # type: list[str] | str | None
    modified_files=None,  # type: list[str] | str | None
    ignore_component_dependencies_file_patterns=None,  # type: list[str] | str | None
):  # type: (...) -> (int, list[App]) | int
    """
    Build all the specified apps

    :param apps: list of apps to be built
    :type apps: list[App] | App
    :param build_verbose: call ``--verbose`` in ``idf.py build`` or not
    :type build_verbose: bool
    :param parallel_count: number of parallel tasks to run
    :type parallel_count: int
    :param parallel_index: index of the parallel task to run
    :type parallel_index: int
    :param dry_run: simulate this run or not
    :type dry_run: bool
    :param keep_going: keep building or not if one app's build failed
    :type keep_going: bool
    :param collect_size_info: file path to record all generated size files' paths if specified
    :type collect_size_info: TextIO | None
    :param collect_app_info: file path to record all the built apps' info if specified
    :type collect_app_info: TextIO | None
    :param ignore_warning_strs: ignore build warnings that matches any of the specified regex patterns
    :type ignore_warning_strs: list[str] | None
    :param ignore_warning_file: ignore build warnings that matches any of the lines of the regex patterns in the
        specified file
    :type ignore_warning_file: list[str] | None
    :param copy_sdkconfig: copy the sdkconfig file to the build directory or not
    :type copy_sdkconfig: bool
    :param manifest_rootpath: The root path of the manifest files. Usually the folders specified in the manifest files
        are relative paths. Use the current directory if not specified
    :type manifest_rootpath: str | None
    :param modified_components: modified components
    :type modified_components: list[str] | str | None
    :param modified_files: modified files
    :type modified_files: list[str] | str | None
    :param ignore_component_dependencies_file_patterns: file patterns that used for ignoring checking the component
        dependencies
    :type ignore_component_dependencies_file_patterns: list[str] | str | None
    :return: (exit_code, built_apps) if specified ``modified_components``
    :rtype: int, list[App]
    :return: exit_code if not specified ``modified_components``
    :rtype: int
    """
    apps = to_list(apps)  # type: list[App]
    modified_components = to_list(modified_components)
    modified_files = to_list(modified_files)
    ignore_component_dependencies_file_patterns = to_list(ignore_component_dependencies_file_patterns)

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

    failed_apps = []
    exit_code = 0

    LOGGER.info('Building the following apps:')
    if apps[start - 1 : stop]:
        for app in apps[start - 1 : stop]:
            LOGGER.info('  %s (preserve: %s)', app, app.preserve)
    else:
        LOGGER.info('  parallel count is too large. build nothing...')

    # cleanup collect files if exists at this early-stage
    collect_files = []
    for app in apps[start - 1 : stop]:  # we use 1-based
        app.parallel_index = parallel_index
        app.parallel_count = parallel_count

        if collect_app_info:
            if isinstance(collect_app_info, io.TextIOWrapper):
                warnings.warn(
                    '"collect_app_info" does not support file stream in idf-build-apps 1.0.0, Please use str instead',
                    DeprecationWarning,
                )
                app._collect_app_info = collect_app_info.name
            else:
                app._collect_app_info = collect_app_info

            if app.collect_app_info not in collect_files:
                collect_files.append(app.collect_app_info)

        if collect_size_info:
            if isinstance(collect_size_info, io.TextIOWrapper):
                warnings.warn(
                    '"collect_size_info" does not support file stream in idf-build-apps 1.0.0, Please use str instead',
                    DeprecationWarning,
                )
                app._collect_size_info = collect_size_info.name
            else:
                app._collect_size_info = collect_size_info

            if app.collect_size_info not in collect_files:
                collect_files.append(app.collect_size_info)

    for f in collect_files:
        if os.path.isfile(f):
            os.remove(f)
            LOGGER.info('=> Remove existing collect file %s', f)
        Path(f).touch()

    actual_built_apps = []
    built_apps = []  # type: list[App]
    skipped_apps = []  # type: list[App]
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
            is_built = app.build(
                modified_components=modified_components,
                check_component_dependencies=_check_components_dependency(
                    manifest_rootpath, modified_components, modified_files, ignore_component_dependencies_file_patterns
                ),
                is_modified=app.is_modified(modified_files),
            )
        except BuildError as e:
            LOGGER.error(str(e))
            if keep_going:
                failed_apps.append(app)
                exit_code = 1
            else:
                if modified_components is not None:
                    return 1, actual_built_apps
                else:
                    return 1
        finally:
            if is_built:
                built_apps.append(app)
            else:
                skipped_apps.append(app)

            if is_built:
                actual_built_apps.append(app)

                if app.collect_app_info:
                    with open(app.collect_app_info, 'a') as fw:
                        fw.write(app.to_json() + '\n')
                    LOGGER.info('=> Recorded app info in %s', app.collect_app_info)

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

    if built_apps:
        LOGGER.info('Built the following apps:')
        for app in built_apps:
            LOGGER.info('  %s', app)

    if skipped_apps:
        LOGGER.info('Skipped the following apps:')
        for app in skipped_apps:
            LOGGER.info('  %s', app)

    if failed_apps:
        LOGGER.error('Build failed for the following apps:')
        for app in failed_apps:
            LOGGER.error('  %s', app)

    if modified_components is not None:
        return exit_code, actual_built_apps
    else:
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

            if isinstance(action, argparse._AppendAction):  # noqa
                _help += (
                    '. Could be specified for multiple times'
                    '{} ! DeprecationWarning: will change to space-separated list in idf-build-apps 1.0.0 version'.format(
                        self.LINE_SEP
                    )
                )
                _type = 'list[{}]'.format(default_type.__name__)
            elif action.nargs in [argparse.ZERO_OR_MORE, argparse.ONE_OR_MORE]:
                _type = 'list[{}]'.format(default_type.__name__)
            else:
                _type = default_type.__name__

            defaulting_nargs = [argparse.OPTIONAL, argparse.ZERO_OR_MORE]
            if action.option_strings or action.nargs in defaulting_nargs:
                _help += '{} - default: %(default)s'.format(self.LINE_SEP)

            _help += '{} - config name: {}'.format(self.LINE_SEP, action.dest)
            _help += '{} - config type: {}'.format(self.LINE_SEP, _type)

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
    common_args.add_argument(
        '--exclude',
        action='append',
        help='Ignore specified directory (if --recursive is given)',
    )
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
        help='Relative to build dir. The build log will be written to this file instead of sys.stdout if specified. Can expand placeholders',
    )
    common_args.add_argument(
        '--size-file',
        help='Relative to build dir. The size json will be written to this file if specified. Can expand placeholders',
    )
    common_args.add_argument(
        '--config',
        action='append',
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
        'By default set to WARNING level. Specify once to set to INFO level. Specify twice or more to set to DEBUG level',
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
        action='append',
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
        '(except preview ones) would be used if this option is not set.'
        '{} ! DeprecationWarning: comma-separated list support will be removed in idf-build-apps 1.0.0 version'.format(
            IdfBuildAppsCliFormatter.LINE_SEP
        ),
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
        '--ignore-component-dependencies-file-patterns',
        nargs='*',
        default=None,
        help='space-separated list which specifies the file patterns used for ignoring the component dependencies. '
        'The `depends_components` and `depends_filepatterns` set in the manifest files will be ignored when any of '
        'the specified file patterns matches any of the modified files. Must be used together with '
        '--modified-files',
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
        help='write size info json file while building into the specified file. each line is a json object. Can expand placeholders',
    )
    build_parser.add_argument(
        '--collect-app-info',
        help='write app info json file while building into the specified file. each line is a json object. Can expand placeholders',
    )
    build_parser.add_argument(
        '--ignore-warning-str',
        action='append',
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
            t_list = [_t.strip() for _t in target.split(',')] if ',' in target else [target.strip()]
            for _t in t_list:
                if _t not in ALL_TARGETS:
                    raise InvalidCommand(
                        'Unrecognizable target {} specified with "--default-build-targets". '
                        'Current ESP-IDF available targets: {}'.format(_t, ALL_TARGETS)
                    )

                if _t not in default_build_targets:
                    default_build_targets.append(_t)

    args.default_build_targets = default_build_targets

    if args.ignore_component_dependencies_file_patterns:
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
        ignore_component_dependencies_file_patterns=args.ignore_component_dependencies_file_patterns,
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
        manifest_rootpath=args.manifest_rootpath,
        modified_components=args.modified_components,
        modified_files=args.modified_files,
        ignore_component_dependencies_file_patterns=args.ignore_component_dependencies_file_patterns,
    )

    if args.modified_components is not None:
        sys.exit(res[0])
    else:
        sys.exit(res)
