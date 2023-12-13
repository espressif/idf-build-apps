# SPDX-FileCopyrightText: 2022-2023 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import logging
import os
import re
import typing as t
from pathlib import (
    Path,
)

from .app import (
    App,
    CMakeApp,
)
from .constants import (
    BuildStatus,
)
from .utils import (
    config_rules_from_str,
    to_absolute_path,
    to_list,
)

LOGGER = logging.getLogger(__name__)


def _get_apps_from_path(
    path: str,
    target: str,
    app_cls: t.Type[App] = CMakeApp,
    work_dir: t.Optional[str] = None,
    build_dir: str = 'build',
    config_rules_str: t.Optional[t.List[str]] = None,
    build_log_filename: t.Optional[str] = None,
    size_json_filename: t.Optional[str] = None,
    check_warnings: bool = False,
    preserve: bool = True,
    manifest_rootpath: t.Optional[str] = None,
    modified_components: t.Optional[t.List[str]] = None,
    modified_files: t.Optional[t.List[str]] = None,
    check_app_dependencies: bool = False,
    sdkconfig_defaults_str: t.Optional[str] = None,
    include_skipped_apps: bool = False,
) -> t.List[App]:
    modified_components = to_list(modified_components)
    modified_files = to_list(modified_files)

    def _validate_app(_app: App) -> bool:
        if target not in _app.supported_targets:
            LOGGER.debug('=> Ignored. %s only supports targets: %s', _app, ', '.join(_app.supported_targets))
            return False

        _app._check_should_build(
            manifest_rootpath=manifest_rootpath,
            modified_components=modified_components,
            modified_files=modified_files,
            check_app_dependencies=check_app_dependencies,
        )

        # for unknown ones, we keep them to the build stage to judge
        if _app.build_status == BuildStatus.SKIPPED:
            return include_skipped_apps

        return True

    if not app_cls.is_app(path):
        LOGGER.debug('Skipping. %s is not an app', path)
        return []

    config_rules = config_rules_from_str(config_rules_str)
    if not config_rules:
        config_rules = []

    apps = []
    default_config_name = ''
    sdkconfig_paths_matched = False
    for rule in config_rules:
        if not rule.file_name:
            default_config_name = rule.config_name
            continue

        sdkconfig_paths = sorted([str(p.relative_to(path)) for p in Path(path).glob(rule.file_name)])

        if sdkconfig_paths:
            sdkconfig_paths_matched = True  # skip the next block for no wildcard config rules

        for sdkconfig_path in sdkconfig_paths:
            if sdkconfig_path.endswith(f'.{target}'):
                LOGGER.debug('=> Skipping sdkconfig %s which is target-specific', sdkconfig_path)
                continue

            # Figure out the config name
            config_name = rule.config_name or ''
            if '*' in rule.file_name:
                # convert glob pattern into a regex
                regex_str = r'.*' + rule.file_name.replace('.', r'\.').replace('*', r'(.*)')
                groups = re.match(regex_str, sdkconfig_path)
                assert groups
                config_name = groups.group(1)

            app = app_cls(
                path,
                target,
                sdkconfig_path=sdkconfig_path,
                config_name=config_name,
                work_dir=work_dir,
                build_dir=build_dir,
                build_log_filename=build_log_filename,
                size_json_filename=size_json_filename,
                check_warnings=check_warnings,
                preserve=preserve,
                sdkconfig_defaults_str=sdkconfig_defaults_str,
            )
            if _validate_app(app):
                LOGGER.debug('Found app: %s', app)
                apps.append(app)

            LOGGER.debug('')  # add one empty line for separating different finds

    # no config rules matched, use default app
    if not sdkconfig_paths_matched:
        app = app_cls(
            path,
            target,
            sdkconfig_path=None,
            config_name=default_config_name,
            work_dir=work_dir,
            build_dir=build_dir,
            build_log_filename=build_log_filename,
            size_json_filename=size_json_filename,
            check_warnings=check_warnings,
            preserve=preserve,
            sdkconfig_defaults_str=sdkconfig_defaults_str,
        )

        if _validate_app(app):
            LOGGER.debug('Found app: %s', app)
            apps.append(app)

        LOGGER.debug('')  # add one empty line for separating different finds

    return sorted(apps)


def _find_apps(
    path: str,
    target: str,
    app_cls: t.Type[App] = CMakeApp,
    recursive: bool = False,
    exclude_list: t.Optional[t.List[str]] = None,
    **kwargs,
) -> t.List[App]:
    exclude_list = exclude_list or []
    LOGGER.debug(
        'Looking for %s apps in %s%s with target %s',
        app_cls.__name__,
        path,
        ' recursively' if recursive else '',
        target,
    )

    if not recursive:
        if exclude_list:
            LOGGER.warning('--exclude option is ignored when used without --recursive')

        return _get_apps_from_path(path, target, app_cls, **kwargs)

    # The remaining part is for recursive == True
    apps = []
    # handle the exclude list, since the config file might use linux style, but run in windows
    exclude_paths_list = [to_absolute_path(p) for p in exclude_list]
    for root, dirs, _ in os.walk(path):
        LOGGER.debug('Entering %s', root)
        root_path = to_absolute_path(root)
        if root_path in exclude_paths_list:
            LOGGER.debug('=> Skipping %s (excluded)', root)
            del dirs[:]
            continue

        if root_path.parts[-1] == 'managed_components':  # idf-component-manager
            LOGGER.debug('=> Skipping %s (managed components)', root_path)
            del dirs[:]
            continue

        _found_apps = _get_apps_from_path(root, target, app_cls, **kwargs)
        if _found_apps:  # root has at least one app
            LOGGER.debug('=> Stop iteration sub dirs of %s since it has apps', root)
            del dirs[:]
            apps.extend(_found_apps)
            continue

    return apps
