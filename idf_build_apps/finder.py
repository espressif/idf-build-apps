# SPDX-FileCopyrightText: 2022-2025 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import logging
import os
import os.path
import re
import typing as t
from pathlib import (
    Path,
)

from .app import (
    App,
    CMakeApp,
)
from .args import FindArguments
from .constants import (
    BuildStatus,
)
from .manifest.manifest import DEFAULT_BUILD_TARGETS
from .utils import (
    config_rules_from_str,
    to_absolute_path,
)

LOGGER = logging.getLogger(__name__)


def _get_apps_from_path(
    path: str,
    target: str,
    *,
    app_cls: t.Type[App] = CMakeApp,
    args: FindArguments,
) -> t.List[App]:
    def _validate_app(_app: App) -> bool:
        if target not in _app.supported_targets:
            LOGGER.debug('=> Ignored. %s only supports targets: %s', _app, ', '.join(_app.supported_targets))
            _app.build_status = BuildStatus.DISABLED
            return args.include_disabled_apps

        if target == 'all' and _app.target not in DEFAULT_BUILD_TARGETS.get():
            LOGGER.debug(
                '=> Ignored. %s is not in the default build targets: %s', _app.target, DEFAULT_BUILD_TARGETS.get()
            )
            _app.build_status = BuildStatus.DISABLED
            return args.include_disabled_apps
        elif _app.target != target:
            LOGGER.debug('=> Ignored. %s is not for target %s', _app, target)
            _app.build_status = BuildStatus.DISABLED
            return args.include_disabled_apps

        _app.check_should_build(
            manifest_rootpath=args.manifest_rootpath,
            modified_manifest_rules_folders=args.modified_manifest_rules_folders,
            modified_components=args.modified_components,
            modified_files=args.modified_files,
            check_app_dependencies=args.dependency_driven_build_enabled,
        )

        # for unknown ones, we keep them to the build stage to judge
        if _app.build_status == BuildStatus.SKIPPED:
            LOGGER.debug('=> Skipped. Reason: %s', _app.build_comment or 'Unknown')
            return args.include_skipped_apps

        return True

    if not app_cls.is_app(path):
        LOGGER.debug('Skipping. %s is not an app', path)
        return []

    config_rules = config_rules_from_str(args.config_rules)

    apps = []
    default_config_name = ''
    sdkconfig_paths_matched = False
    for rule in config_rules:
        if not rule.file_name:
            default_config_name = rule.config_name
            continue

        sdkconfig_paths = sorted([str(p.resolve()) for p in Path(path).glob(rule.file_name)])

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
                work_dir=args.work_dir,
                build_dir=args.build_dir,
                build_log_filename=args.build_log_filename,
                size_json_filename=args.size_json_filename,
                check_warnings=args.check_warnings,
                sdkconfig_defaults_str=args.sdkconfig_defaults,
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
            work_dir=args.work_dir,
            build_dir=args.build_dir,
            build_log_filename=args.build_log_filename,
            size_json_filename=args.size_json_filename,
            check_warnings=args.check_warnings,
            sdkconfig_defaults_str=args.sdkconfig_defaults,
        )

        if _validate_app(app):
            LOGGER.debug('Found app: %s', app)
            apps.append(app)

        LOGGER.debug('')  # add one empty line for separating different finds

    return sorted(apps)


def _find_apps(
    path: str,
    target: str,
    *,
    app_cls: t.Type[App] = CMakeApp,
    args: FindArguments,
) -> t.List[App]:
    LOGGER.debug(
        'Looking for %s apps in %s%s with target %s',
        app_cls.__name__,
        path,
        ' recursively' if args.recursive else '',
        target,
    )

    if not args.recursive:
        if args.exclude:
            LOGGER.debug('--exclude option is ignored when used without --recursive')

        return _get_apps_from_path(path, target, app_cls=app_cls, args=args)

    # The remaining part is for recursive == True
    apps = []
    # handle the exclude list, since the config file might use linux style, but run in windows
    exclude_paths_list = [to_absolute_path(p) for p in args.exclude or []]
    for root, dirs, _ in os.walk(path):
        LOGGER.debug('Entering %s', root)
        root_path = to_absolute_path(root)
        if root_path in exclude_paths_list:
            LOGGER.debug('=> Skipping %s (excluded)', root)
            del dirs[:]
            continue

        if os.path.basename(root_path) == 'managed_components':  # idf-component-manager
            LOGGER.debug('=> Skipping %s (managed components)', root_path)
            del dirs[:]
            continue

        _found_apps = _get_apps_from_path(root, target, app_cls=app_cls, args=args)
        if _found_apps:  # root has at least one app
            LOGGER.debug('=> Stop iteration sub dirs of %s since it has apps', root)
            del dirs[:]
            apps.extend(_found_apps)
            continue

    return apps
