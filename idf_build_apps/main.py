# SPDX-FileCopyrightText: 2022 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0
import os
import re
import shutil

from . import LOGGER
from .app import App
from .constants import ALL_TARGETS
from .finder import _find_apps
from .manifest.manifest import FolderRule, Manifest
from .utils import BuildError, get_parallel_start_stop

try:
    import typing as t
except ImportError:
    pass


def find_apps(
    paths,  # type: (list[str] | str)
    target,  # type: str
    build_system='cmake',  # type: str
    recursive=False,  # type: bool
    exclude_list=None,  # type: list[str] | None
    work_dir=None,  # type: str | None
    build_dir='build',  # type: str
    config_rules_str=None,  # type: list[str] | None
    build_log_path=None,  # type: str | None
    size_json_path=None,  # type: str | None
    check_warnings=False,  # type: bool
    preserve=True,  # type: bool
    manifest_files=None,  # type: list[str] | str | None
    default_build_targets=None,  # type: list[str] | str | None
    depends_on_components=None,  # type: list[str] | str | None
):  # type: (...) -> list[App]
    if default_build_targets:
        if isinstance(default_build_targets, str):
            default_build_targets = [default_build_targets]

        LOGGER.info('Overriding DEFAULT_BUILD_TARGETS to %s', default_build_targets)
        FolderRule.DEFAULT_BUILD_TARGETS = default_build_targets

    if manifest_files:
        if isinstance(manifest_files, str):
            manifest_files = [manifest_files]

        rules = set()
        for _manifest_file in manifest_files:
            LOGGER.info('Loading manifest file: %s', _manifest_file)
            rules.update(Manifest.from_file(_manifest_file).rules)
        manifest = Manifest(rules)
        App.MANIFEST = manifest

    apps = []
    if isinstance(paths, str):
        paths = [paths]

    if target == 'all':
        targets = ALL_TARGETS
    else:
        targets = [target]

    if isinstance(depends_on_components, str):
        depends_on_components = [depends_on_components]

    for target in targets:
        for path in paths:
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
                    depends_on_components=depends_on_components,
                )
            )
    apps.sort()

    LOGGER.info('Found %d apps in total', len(apps))
    return apps


def build_apps(
    apps,  # type: list[App]
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
):  # type: (...) -> t.Tuple[int, list[App]] | int
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

    actual_built_apps = []
    for i, app in enumerate(apps):
        index = i + 1  # we use 1-based
        if index < start or index > stop:
            continue

        # attrs
        app.dry_run = dry_run
        app.index = index
        app.verbose = build_verbose

        LOGGER.debug('=> Building app %s: %s', index, repr(app))
        is_built = False
        try:
            is_built = app.build(depends_on_components)
        except BuildError as e:
            LOGGER.error(str(e))
            if keep_going:
                failed_apps.append(app)
                exit_code = 1
            else:
                if depends_on_components:
                    return 1, actual_built_apps
                else:
                    return 1
        finally:
            if is_built:
                actual_built_apps.append(app)

            if collect_app_info:
                collect_app_info.write(app.to_json() + '\n')

            if collect_size_info:
                try:
                    # this may not work if the build is failed
                    app.collect_size_info(collect_size_info)
                except Exception as e:
                    LOGGER.debug(e)
                    pass

            if copy_sdkconfig:
                try:
                    shutil.copy(
                        os.path.join(app.work_dir, 'sdkconfig'),
                        os.path.join(app.build_path, 'sdkconfig'),
                    )
                except Exception as e:
                    LOGGER.debug(e)
                    pass

    if failed_apps:
        LOGGER.error('Build failed for the following apps:')
        for app in failed_apps:
            LOGGER.error('  %s', app)

    if depends_on_components:
        return exit_code, actual_built_apps
    else:
        return exit_code
