# SPDX-FileCopyrightText: 2022-2023 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0
import os
import re
import shutil
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
    files_matches_patterns,
    get_parallel_start_stop,
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
    if depends_on_components is None:
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
