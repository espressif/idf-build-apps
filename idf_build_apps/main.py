# SPDX-FileCopyrightText: 2022 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0
import logging
import os
import re
import shutil

from . import LOGGER
from .app import App
from .constants import ALL_TARGETS
from .finder import _find_apps
from .manifest.manifest import Manifest, FolderRule
from .utils import get_parallel_start_stop, BuildError

try:
    from typing import TextIO
except ImportError:
    pass


def find_apps(
    paths,
    target,
    build_system='cmake',
    recursive=False,
    exclude_list=None,
    work_dir=None,
    build_dir='build',
    config_rules_str=None,
    build_log_path=None,
    size_json_path=None,
    check_warnings=False,
    preserve=True,
    manifest_files=None,
    default_build_targets=None,
):  # type: (list[str] | str, str, str, bool, list[str] | None, str | None, str, list[str] | None, str | None, str | None, bool, bool, list[str] | str | None, list[str] | str | None) -> list[App]
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
                )
            )
    apps.sort()

    LOGGER.info('Found %d apps in total', len(apps))
    return apps


def build_apps(
    apps,
    build_verbose=False,
    parallel_count=1,
    parallel_index=1,
    dry_run=False,
    keep_going=False,
    collect_size_info=None,
    collect_app_info=None,
    ignore_warning_strs=None,
    ignore_warning_file=None,
    copy_sdkconfig=False,
):  # type: (list[App], bool, int, int, bool, bool, TextIO | None, TextIO | None, list[str] | None, TextIO | None, bool) -> int
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

    for i, app in enumerate(apps):
        index = i + 1  # we use 1-based
        if index < start or index > stop:
            continue

        # attrs
        app.dry_run = dry_run
        app.index = index
        app.verbose = build_verbose

        LOGGER.debug('=> Building app %s: %s', index, repr(app))
        try:
            app.build()
        except BuildError as e:
            LOGGER.error(str(e))
            if keep_going:
                failed_apps.append(app)
                exit_code = 1
            else:
                return 1
        finally:
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
            logging.error('  %s', app)

    return exit_code
