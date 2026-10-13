# SPDX-FileCopyrightText: 2022-2026 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import logging
import os
import os.path
import re
import typing as t
from pathlib import Path

from .app import App
from .app import CMakeApp
from .app import _existing_sdkconfig_files
from .app import _sdkconfig_defaults_candidates
from .app import _sdkconfig_target_from_match
from .app import _sdkconfig_target_with_overrides
from .args import FindArguments
from .constants import ALL_TARGETS
from .constants import BuildStatus
from .utils import config_rules_from_str
from .utils import to_absolute_path

LOGGER = logging.getLogger(__name__)


def _is_target_specific(filepath: str) -> bool:
    for target in ALL_TARGETS:
        if filepath.endswith(f'.{target}'):
            return True

    return False


def find_app_configs(
    path: str,
    config_rules: t.Optional[t.List[str]] = None,
    *,
    target: t.Optional[str] = None,
    sdkconfig_defaults: t.Optional[str] = None,
) -> t.List[t.Tuple[t.Optional[str], str]]:
    """Resolve sdkconfig files and names without constructing App objects.

    When target is given, reject configurations that explicitly specify another
    CONFIG_IDF_TARGET in their sdkconfig defaults or selected config file.
    """
    app_configs: t.List[t.Tuple[t.Optional[str], str]] = []  # List of (sdkconfig_path, config_name) tuples
    default_config_name = ''
    sdkconfig_paths_matched = False
    parsed_rules = config_rules_from_str(config_rules)

    for rule in parsed_rules:
        if rule.negated:
            continue

        if not rule.file_name:
            default_config_name = rule.config_name
            continue

        sdkconfig_paths = sorted([str(p.resolve()) for p in Path(path).glob(rule.file_name)])

        if sdkconfig_paths:
            sdkconfig_paths_matched = True  # skip the next block for no wildcard config rules

        for sdkconfig_path in sdkconfig_paths:
            if _is_target_specific(sdkconfig_path):
                LOGGER.debug('=> Skipping sdkconfig file `%s` which is target-specific', sdkconfig_path)
                continue

            # Figure out the config name
            config_name = rule.config_name or ''
            if '*' in rule.file_name:
                # convert glob pattern into a regex
                regex_str = r'.*' + rule.file_name.replace('.', r'\.').replace('*', r'(.*)')
                groups = re.match(regex_str, sdkconfig_path)
                assert groups
                config_name = groups.group(1)

            app_configs.append((sdkconfig_path, config_name))

    # Apply negation rules
    negated_paths: t.Set[str] = set()
    for rule in parsed_rules:
        if not rule.negated:
            continue
        for matched in Path(path).glob(rule.file_name):
            negated_paths.add(str(matched.resolve()))

    if negated_paths:
        app_configs = [(p, n) for p, n in app_configs if p not in negated_paths]

    # no config rules matched, use default app
    if not sdkconfig_paths_matched:
        app_configs.append((None, default_config_name))

    if target is None:
        return app_configs

    defaults = _sdkconfig_defaults_candidates(sdkconfig_defaults)
    matching_configs: t.List[t.Tuple[t.Optional[str], str]] = []
    for selected_path, config_name in app_configs:
        defined_target = None
        for candidate in _existing_sdkconfig_files(path, defaults, selected_path):
            with open(candidate) as fr:
                for line in fr:
                    file_target = _sdkconfig_target_from_match(App.SDKCONFIG_LINE_REGEX.match(os.path.expandvars(line)))
                    if file_target is not None:
                        defined_target = file_target
        defined_target = _sdkconfig_target_with_overrides(defined_target)
        if defined_target is None or defined_target == target:
            matching_configs.append((selected_path, config_name))

    return matching_configs


def _get_apps_from_path(
    path: str,
    target: str,
    *,
    app_cls: t.Type[App] = CMakeApp,
    args: FindArguments,
) -> t.List[App]:
    if not app_cls.is_app(path):
        LOGGER.debug('Skipping. %s is not an app', path)
        return []

    apps = []
    # Create, validate, and add all apps
    for p, n in find_app_configs(path, args.config_rules):
        app = app_cls(
            path,
            target,
            sdkconfig_path=p,
            config_name=n,
            work_dir=args.work_dir,
            build_dir=args.build_dir,
            build_log_filename=args.build_log_filename,
            size_json_filename=args.size_json_filename,
            size_json_extra_args=args.size_json_extra_args,
            check_warnings=args.check_warnings,
            sdkconfig_defaults_str=args.sdkconfig_defaults,
        )

        if app.sdkconfig_files_defined_idf_target and app.target != app.sdkconfig_files_defined_idf_target:
            LOGGER.debug(
                'Project %s with config %s defined CONFIG_IDF_TARGET=%s, Ignoring target %s',
                app.app_dir,
                app.config_name or 'default',
                app.sdkconfig_files_defined_idf_target,
                target,
            )
            continue

        app.check_should_build(
            manifest_rootpath=args.manifest_rootpath,
            modified_manifest_rules_folders=args.modified_manifest_rules_folders,
            modified_components=args.modified_components,
            modified_files=args.modified_files,
            check_app_dependencies=args.dependency_driven_build_enabled,
        )
        app.check_should_test()

        if app.build_status == BuildStatus.DISABLED:
            LOGGER.debug('=> Disabled. Reason: %s', app.build_comment or 'Unknown')
            should_include = args.include_disabled_apps
        elif app.build_status == BuildStatus.SKIPPED:
            LOGGER.debug('=> Skipped. Reason: %s', app.build_comment or 'Unknown')
            should_include = args.include_skipped_apps
        else:
            should_include = True

        if should_include:
            LOGGER.debug('Found app: %s', app)
            apps.append(app)

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
