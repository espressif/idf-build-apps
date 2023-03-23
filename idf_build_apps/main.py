# SPDX-FileCopyrightText: 2022-2023 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0
import argparse
import os
import re
import shutil
import sys
from pathlib import (
    Path,
)

from . import (
    LOGGER,
)
from .app import (
    App,
)
from .constants import (
    ALL_TARGETS,
)
from .finder import (
    _find_apps,
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
    setup_logging,
    to_list,
)

try:
    import typing as t
except ImportError:
    pass


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
    manifest_files=None,  # type: list[str] | str | None
    default_build_targets=None,  # type: list[str] | str | None
    depends_on_components=None,  # type: list[str] | str | None
    manifest_rootpath=None,  # type: str | None
    ignore_component_dependencies_file_patterns=None,  # type: list[str] | str | None
    depends_on_files=None,  # type: list[str] | str | None
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
    :param manifest_files: paths of the manifest files
    :type manifest_files: list[str] | str | None
    :param default_build_targets: default build targets used in manifest files
    :type default_build_targets: list[str] | str | None
    :param depends_on_components: app with ``requires_components`` set in the corresponding manifest files will only
        be built if it depends on any of the specified components
    :type depends_on_components: list[str] | str | None
    :param manifest_rootpath: The root path of the manifest files. Usually the folders specified in the manifest files
        are relative paths. Use the current directory if not specified
    :type manifest_rootpath: str | None
    :param ignore_component_dependencies_file_patterns: file patterns that use to ignore checking the component
        dependencies
    :type ignore_component_dependencies_file_patterns: list[str] | str | None
    :param depends_on_files: skip check app's component dependencies if any of the specified files matches
        ``ignore_component_dependencies_file_patterns``
    :type depends_on_files: list[str] | str | None
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
    Manifest.ROOTPATH = Path(manifest_rootpath or os.curdir).resolve()

    if manifest_files:
        rules = set()
        for _manifest_file in to_list(manifest_files):
            LOGGER.debug('Loading manifest file: %s', _manifest_file)
            rules.update(Manifest.from_file(_manifest_file).rules)
        manifest = Manifest(rules)
        App.MANIFEST = manifest

    depends_on_components = to_list(depends_on_components)
    if depends_on_components is None:
        check_component_dependencies = False
    elif (
        ignore_component_dependencies_file_patterns
        and depends_on_files
        and files_matches_patterns(depends_on_files, ignore_component_dependencies_file_patterns)
    ):
        LOGGER.debug(
            'Skipping check component dependencies for apps since files %s matches patterns: %s',
            ', '.join(depends_on_files),
            ', '.join(ignore_component_dependencies_file_patterns),
        )
        check_component_dependencies = False
    else:
        check_component_dependencies = True

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
                    depends_on_components=depends_on_components,
                    check_component_dependencies=check_component_dependencies,
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
    collect_size_info=None,  # type: t.TextIO | None
    collect_app_info=None,  # type: t.TextIO | None
    ignore_warning_strs=None,  # type: list[str] | None
    ignore_warning_file=None,  # type: t.TextIO | None
    copy_sdkconfig=False,  # type: bool
    depends_on_components=None,  # type: list[str] | str | None
    manifest_rootpath=None,  # type: str | None
    ignore_component_dependencies_file_patterns=None,  # type: list[str] | str | None
    depends_on_files=None,  # type: list[str] | str | None
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
    :param depends_on_components: app with ``requires_components`` set in the corresponding manifest files would only be
        built if it depends on any of the specified components
    :type depends_on_components: list[str] | str | None
    :param manifest_rootpath: The root path of the manifest files. Usually the folders specified in the manifest files
        are relative paths. Use the current directory if not specified
    :type manifest_rootpath: str | None
    :param ignore_component_dependencies_file_patterns: file patterns that use to ignore checking the component
        dependencies
    :type ignore_component_dependencies_file_patterns: list[str] | str | None
    :param depends_on_files: skip check app's component dependencies if any of the specified files matches
        ``ignore_component_dependencies_file_patterns``
    :type depends_on_files: list[str] | str | None
    :return: exit_code, built_apps if specified ``depends_on_components``
    :rtype: int, list[App]
    :return: exit_code if not specified ``depends_on_components``
    :rtype: int
    """
    apps = to_list(apps)

    ignore_warnings_regexes = []
    if ignore_warning_strs:
        for s in ignore_warning_strs:
            ignore_warnings_regexes.append(re.compile(s))
    if ignore_warning_file:
        for s in ignore_warning_file:
            ignore_warnings_regexes.append(re.compile(s.strip()))
    App.IGNORE_WARNS_REGEXES = ignore_warnings_regexes

    depends_on_components = to_list(depends_on_components)
    # here depends_on_components [''] means that the user use --depends-on-components
    # the ones with `requires_components` are already been filtered out
    # if we skip all build, that would be too aggressive
    if depends_on_components is None or depends_on_components == ['']:
        check_component_dependencies = False
    elif (
        ignore_component_dependencies_file_patterns
        and depends_on_files
        and files_matches_patterns(depends_on_files, ignore_component_dependencies_file_patterns, manifest_rootpath)
    ):
        LOGGER.debug(
            'Skipping check component dependencies for apps since files %s matches patterns: %s',
            ', '.join(depends_on_files),
            ', '.join(ignore_component_dependencies_file_patterns),
        )
        check_component_dependencies = False
    else:
        check_component_dependencies = True

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

    actual_built_apps = []
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
                depends_on_components=depends_on_components,
                check_component_dependencies=check_component_dependencies,
            )
        except BuildError as e:
            LOGGER.error(str(e))
            if keep_going:
                failed_apps.append(app)
                exit_code = 1
            else:
                if depends_on_components is not None:
                    return 1, actual_built_apps
                else:
                    return 1
        finally:
            if is_built:
                actual_built_apps.append(app)

                if collect_app_info:
                    collect_app_info.write(app.to_json() + '\n')
                    LOGGER.info('=> Recorded app info in %s', collect_app_info.name)

                if collect_size_info:
                    try:
                        app.collect_size_info(collect_size_info)
                    except Exception as e:
                        LOGGER.warning('Adding size info for app %s failed:', app.name)
                        LOGGER.warning(e)
                        pass

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

    if failed_apps:
        LOGGER.error('Build failed for the following apps:')
        for app in failed_apps:
            LOGGER.error('  %s', app)

    if depends_on_components is not None:
        return exit_code, actual_built_apps
    else:
        return exit_code


def main():
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
        help='Relative to build dir. The build log will be written to this file instead of sys.stdout if specified.'
        'Can expand placeholders.',
    )
    common_args.add_argument(
        '--size-file',
        help='Relative to build dir. The size json will be written to this file if specified. Can expand placeholders.',
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
        '--sdkconfig-defaults',
        help='semicolon-separated string, pass to idf.py -DSDKCONFIG_DEFAULTS if specified, also could be set via '
        'environment variables "SDKCONFIG_DEFAULTS"',
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
        help='comma-separated list of supported targets. Targets supported in current ESP-IDF branch '
        '(except preview ones) would be used if this option is not set',
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

    # validate cli options
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
        for target in args.default_build_targets.split(','):
            target = target.strip()
            if target not in ALL_TARGETS:
                raise InvalidCommand(
                    'Unrecognizable target {} specified with "--default-build-targets". '
                    'Current ESP-IDF available targets: {}'.format(target, ALL_TARGETS)
                )

            if target not in default_build_targets:
                default_build_targets.append(target)

    if (args.ignore_component_dependencies_file_patterns is None) != (args.depends_on_files is None):
        raise InvalidCommand(
            'Must specify both "--ignore-component-dependencies-file-patterns" and "--depends-on-files" '
            'or neither of them'
        )

    # real call starts here
    setup_logging(args.verbose, args.log_file, not args.no_color)

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
        depends_on_components=args.depends_on_components,
        manifest_rootpath=args.manifest_rootpath,
        ignore_component_dependencies_file_patterns=args.ignore_component_dependencies_file_patterns,
        depends_on_files=args.depends_on_files,
    )

    if args.depends_on_components is not None:
        sys.exit(res[0])
    else:
        sys.exit(res)
