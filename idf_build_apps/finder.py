# SPDX-FileCopyrightText: 2022-2023 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import os.path
import re
from pathlib import (
    Path,
)

from . import (
    LOGGER,
)
from .app import (
    App,
    CMakeApp,
)
from .utils import (
    config_rules_from_str,
    to_list,
)


def _get_apps_from_path(
    path,  # type: str
    target,  # type: str
    build_system='cmake',  # type: str
    work_dir=None,  # type: str | None
    build_dir='build',  # type: str
    config_rules_str=None,  # type: list[str] | str | None
    build_log_path=None,  # type: str | None
    size_json_path=None,  # type: str | None
    check_warnings=False,  # type: bool
    preserve=True,  # type: bool
    depends_on_components=None,  # type: list[str] | str | None
    check_component_dependencies=False,  # type: bool
    sdkconfig_defaults_str=None,  # type: str | None
):  # type: (...) -> list[App]
    depends_on_components = to_list(depends_on_components)

    def _validate_app(_app):  # type: (App) -> bool
        if target not in _app.supported_targets:
            LOGGER.debug('=> Skipping. %s only supports targets: %s', _app, ', '.join(_app.supported_targets))
            return False

        if _app.requires_components and check_component_dependencies:
            if not set(_app.requires_components).intersection(set(depends_on_components)):
                LOGGER.debug(
                    '=> Skipping. %s requires components: %s, but you passed "--depends-on-components %s"',
                    _app,
                    ', '.join(_app.requires_components),
                    ', '.join(depends_on_components),
                )
                return False

        return True

    if build_system == 'cmake':
        app_cls = CMakeApp
    else:
        raise ValueError('Only Support CMake for now')

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

        sdkconfig_paths = Path(path).glob(rule.file_name)
        sdkconfig_paths = sorted([str(p.relative_to(path)) for p in sdkconfig_paths])

        if sdkconfig_paths:
            sdkconfig_paths_matched = True  # skip the next block for no wildcard config rules

        for sdkconfig_path in sdkconfig_paths:
            if sdkconfig_path.endswith('.{}'.format(target)):
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
                build_log_path=build_log_path,
                size_json_path=size_json_path,
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
            build_log_path=build_log_path,
            size_json_path=size_json_path,
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
    path,  # type: str
    target,  # type: str
    build_system='cmake',  # type: str
    recursive=False,  # type: bool
    exclude_list=None,  # type: list[str] | None
    **kwargs
):  # type: (...) -> list[App]
    exclude_list = exclude_list or []
    LOGGER.debug(
        'Looking for %s apps in %s%s with target %s', build_system, path, ' recursively' if recursive else '', target
    )

    if not recursive:
        if exclude_list:
            LOGGER.warning('--exclude option is ignored when used without --recursive')

        return _get_apps_from_path(path, target, build_system, **kwargs)

    # The remaining part is for recursive == True
    apps = []
    for root, dirs, _ in os.walk(path):
        LOGGER.debug('Entering %s', root)
        if root in exclude_list:
            LOGGER.debug('=> Skipping %s (excluded)', root)
            del dirs[:]
            continue

        if root.endswith('managed_components'):  # idf-component-manager
            LOGGER.debug('=> Skipping %s (managed components)', root)
            del dirs[:]
            continue

        _found_apps = _get_apps_from_path(root, target, build_system, **kwargs)
        if _found_apps:  # root has at least one app
            LOGGER.debug('=> Stop iteration sub dirs of %s since it has apps', root)
            del dirs[:]
            apps.extend(_found_apps)
            continue

    return apps
