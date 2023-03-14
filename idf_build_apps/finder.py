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
    dict_from_sdkconfig,
    get_sdkconfig_defaults,
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
    if build_system == 'cmake':
        app_cls = CMakeApp
    else:
        raise ValueError('Only Support CMake for now')

    if not app_cls.is_app(path):
        LOGGER.debug('Skipping. %s is not an app', path)
        return []

    sdkconfig_defaults_list = get_sdkconfig_defaults(path, sdkconfig_defaults_str)
    supported_targets = app_cls.enable_build_targets(path, sdkconfig_defaults_list)
    if target not in supported_targets:
        LOGGER.debug('Skipping. %s only supports targets: %s', path, ', '.join(supported_targets))
        return []

    requires_components = app_cls.requires_components(path)
    if requires_components and check_component_dependencies:
        if not set(requires_components).intersection(set(depends_on_components)):
            LOGGER.debug(
                'Skipping. %s requires components: %s, but you passed "--depends-on-components %s"',
                path,
                ', '.join(requires_components),
                ', '.join(depends_on_components),
            )
            return []

    config_rules = config_rules_from_str(config_rules_str)
    if not config_rules:
        config_rules = []

    apps = []
    default_config_name = ''
    for rule in config_rules:
        if not rule.file_name:
            default_config_name = rule.config_name
            continue

        sdkconfig_paths = Path(path).glob(rule.file_name)
        sdkconfig_paths = sorted([str(p) for p in sdkconfig_paths])
        for sdkconfig_path in sdkconfig_paths:
            if sdkconfig_path.endswith('.{}'.format(target)):
                LOGGER.debug('Skipping sdkconfig %s which is target-specific', sdkconfig_path)
                continue

            # Check if the sdkconfig file specifies IDF_TARGET, and if it is matches the --target argument.
            sdkconfig_dict = dict_from_sdkconfig(sdkconfig_path)
            target_from_config = sdkconfig_dict.get('CONFIG_IDF_TARGET')
            if target_from_config is not None and target_from_config != target:
                LOGGER.debug(
                    'Skipping sdkconfig %s which requires target %s',
                    sdkconfig_path,
                    target_from_config,
                )
                continue

            # Figure out the config name
            config_name = rule.config_name or ''
            if '*' in rule.file_name:
                # convert glob pattern into a regex
                regex_str = r'.*' + rule.file_name.replace('.', r'\.').replace('*', r'(.*)')
                groups = re.match(regex_str, sdkconfig_path)
                assert groups
                config_name = groups.group(1)

            sdkconfig_path = os.path.relpath(sdkconfig_path, path)
            LOGGER.debug(
                'Found %s app: %s, sdkconfig %s, config name "%s"',
                build_system,
                path,
                sdkconfig_path,
                config_name,
            )
            apps.append(
                app_cls(
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
                    sdkconfig_defaults_list=sdkconfig_defaults_list,
                )
            )

    # no wildcard config rules
    if not apps:
        LOGGER.debug(
            'Found %s app: %s, default sdkconfig, config name "%s"',
            build_system,
            path,
            default_config_name,
        )
        apps = [
            app_cls(
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
                sdkconfig_defaults_list=sdkconfig_defaults_list,
            )
        ]

    return apps


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
        'Looking for %s apps in %s%s',
        build_system,
        path,
        ' recursively' if recursive else '',
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
