# SPDX-FileCopyrightText: 2022-2023 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import json
import logging
import os
import re
import shutil
import typing as t

import pluggy

from .app import (
    App,
    CMakeApp,
    MakeApp,
)
from .build_apps_args import (
    BuildAppsArgs,
)
from .constants import (
    ALL_TARGETS,
    BuildStatus,
)
from .finder import (
    _find_apps,
)
from .junit import (
    TestCase,
    TestReport,
    TestSuite,
)
from .manifest.manifest import (
    FolderRule,
    Manifest,
)
from .utils import (
    files_matches_patterns,
    get_parallel_start_stop,
    to_absolute_path,
    to_list,
)

LOGGER = logging.getLogger(__name__)

idf_build_apps_hookspec = pluggy.HookspecMarker(__package__)
idf_build_apps_hookimpl = pluggy.HookimplMarker(__package__)


class IdfBuildAppsSpec:
    """
    A specification for idf-build-apps hook functions.

    :warning: All hook functions does not support default value.
        Otherwise, there will be unexpected behavior like kwargs ignored, always use signature default value.
    """

    @idf_build_apps_hookspec(firstresult=True)
    def _check_app_dependency(  # type: ignore
        self,
        manifest_rootpath: t.Optional[str] = None,
        modified_components: t.Optional[t.List[str]] = None,
        modified_files: t.Optional[t.List[str]] = None,
        ignore_app_dependencies_filepatterns: t.Optional[t.List[str]] = None,
    ) -> bool:
        """
        Check app dependencies or not

        :param manifest_rootpath: The root path of the manifest files.
            Usually the folders specified in the manifest files are relative paths.
            Use the current directory if not specified
        :param modified_components: modified components
        :param modified_files: modified files
        :param ignore_app_dependencies_filepatterns: file patterns that used for ignoring checking the component
            dependencies
        :return: True if check app dependencies, otherwise False
        """

    @idf_build_apps_hookspec(firstresult=True)
    def find_apps(  # type: ignore
        self,
        paths: t.Union[t.List[str], str],
        target: str,
        build_system: t.Union[t.Type[App], str],
        recursive: bool,
        exclude_list: t.Optional[t.List[str]],
        work_dir: t.Optional[str],
        build_dir: str,
        config_rules_str: t.Optional[t.Union[t.List[str], str]],
        build_log_filename: t.Optional[str],
        size_json_filename: t.Optional[str],
        check_warnings: bool,
        preserve: bool,
        manifest_rootpath: t.Optional[str],
        manifest_files: t.Optional[t.Union[t.List[str], str]],
        check_manifest_rules: bool,
        default_build_targets: t.Optional[t.Union[t.List[str], str]],
        modified_components: t.Optional[t.Union[t.List[str], str]],
        modified_files: t.Optional[t.Union[t.List[str], str]],
        ignore_app_dependencies_filepatterns: t.Optional[t.Union[t.List[str], str]],
        sdkconfig_defaults: t.Optional[str],
        include_skipped_apps: bool,
    ) -> t.List[App]:
        """
        Find app directories in paths (possibly recursively), which contain apps for the given build system, compatible
        with the given target

        :param paths: list of app directories (can be / usually will be a relative path)
        :param target: desired value of IDF_TARGET; apps incompatible with the given target are skipped.
        :param build_system: class of the build system, default CMakeApp
        :param recursive: Recursively search into the nested sub-folders if no app is found or not
        :param exclude_list: list of paths to be excluded from the recursive search
        :param work_dir: directory where the app should be copied before building. Support placeholders
        :param build_dir: directory where the build will be done. Support placeholders.
        :param config_rules_str: mapping of sdkconfig file name patterns to configuration names
        :param build_log_filename: filename of the build log. Will be placed under the app.build_path.
            Support placeholders. The logs will go to stdout/stderr if not specified
        :param size_json_filename: filename to collect the app's size information.
            Will be placed under the app.build_path.
            Support placeholders. The app's size information won't be collected if not specified
        :param check_warnings: Check for warnings in the build log or not
        :param preserve: Preserve the built binaries or not
        :param manifest_rootpath: The root path of the manifest files.
            Usually the folders specified in the manifest files are relative paths.
            Use the current directory if not specified
        :param manifest_files: paths of the manifest files
        :param check_manifest_rules: check the manifest rules or not
        :param default_build_targets: default build targets used in manifest files
        :param modified_components: modified components
        :param modified_files: modified files
        :param ignore_app_dependencies_filepatterns: file patterns that used for ignoring checking the component
            dependencies
        :param sdkconfig_defaults: semicolon-separated string, pass to idf.py -DSDKCONFIG_DEFAULTS if specified,
            also could be set via environment variables "SDKCONFIG_DEFAULTS"
        :param include_skipped_apps: include skipped apps or not
        :return: list of found apps
        """

    @idf_build_apps_hookspec(firstresult=True)
    def build_apps(  # type: ignore
        self,
        apps: t.Union[t.List[App], App],
        build_verbose: bool,
        dry_run: bool,
        keep_going: bool,
        ignore_warning_strs: t.Optional[t.List[str]],
        ignore_warning_file: t.Optional[t.TextIO],
        copy_sdkconfig: bool,
        manifest_rootpath: t.Optional[str],
        modified_components: t.Optional[t.Union[t.List[str], str]],
        modified_files: t.Optional[t.Union[t.List[str], str]],
        ignore_app_dependencies_filepatterns: t.Optional[t.Union[t.List[str], str]],
        check_app_dependencies: t.Optional[bool],
        # BuildAppsArgs
        parallel_count: int,
        parallel_index: int,
        collect_size_info: t.Optional[str],
        collect_app_info: t.Optional[str],
        junitxml: t.Optional[str],
    ) -> int:
        """
        Build all the specified apps

        :param apps: list of apps to be built
        :param build_verbose: call ``--verbose`` in ``idf.py build`` or not
        :param dry_run: simulate this run or not
        :param keep_going: keep building or not if one app's build failed
        :param ignore_warning_strs: ignore build warnings that matches any of the specified regex patterns
        :param ignore_warning_file: ignore build warnings that matches any of the lines of the regex patterns in the
            specified file
        :param copy_sdkconfig: copy the sdkconfig file to the build directory or not
        :param manifest_rootpath: The root path of the manifest files.
            Usually the folders specified in the manifest files are relative paths.
            Use the current directory if not specified
        :param modified_components: modified components
        :param modified_files: modified files
        :param ignore_app_dependencies_filepatterns: file patterns that used for ignoring checking the component
            dependencies
        :param check_app_dependencies: check app dependencies or not. If not set,
            will be calculated by modified_components, modified_files, and ignore_app_dependencies_filepatterns
        :param parallel_count: number of parallel tasks to run
        :param parallel_index: index of the parallel task to run
        :param collect_size_info: file path to record all generated size files' paths if specified
        :param collect_app_info: file path to record all the built apps' info if specified
        :param junitxml: path of the junitxml file
        :return: exit code
        """


class IdfBuildAppsPlugin:
    """
    A default hook implementation
    """

    @idf_build_apps_hookimpl
    def _check_app_dependency(
        self,
        manifest_rootpath: t.Optional[str] = None,
        modified_components: t.Optional[t.List[str]] = None,
        modified_files: t.Optional[t.List[str]] = None,
        ignore_app_dependencies_filepatterns: t.Optional[t.List[str]] = None,
    ) -> bool:
        # not check since modified_components and modified_files are not passed
        if modified_components is None and modified_files is None:
            return False

        # not check since ignore_app_dependencies_filepatterns is passed and matched
        if (
            ignore_app_dependencies_filepatterns
            and modified_files is not None
            and files_matches_patterns(modified_files, ignore_app_dependencies_filepatterns, manifest_rootpath)
        ):
            LOGGER.info(
                'Build all apps since patterns %s matches modified files %s',
                ', '.join(modified_files),
                ', '.join(ignore_app_dependencies_filepatterns),
            )
            return False

        return True

    @idf_build_apps_hookimpl
    def find_apps(
        self,
        paths: t.Union[t.List[str], str],
        target: str,
        build_system: t.Union[t.Type[App], str],
        recursive: bool,
        exclude_list: t.Optional[t.List[str]],
        work_dir: t.Optional[str],
        build_dir: str,
        config_rules_str: t.Optional[t.Union[t.List[str], str]],
        build_log_filename: t.Optional[str],
        size_json_filename: t.Optional[str],
        check_warnings: bool,
        preserve: bool,
        manifest_rootpath: t.Optional[str],
        manifest_files: t.Optional[t.Union[t.List[str], str]],
        check_manifest_rules: bool,
        default_build_targets: t.Optional[t.Union[t.List[str], str]],
        modified_components: t.Optional[t.Union[t.List[str], str]],
        modified_files: t.Optional[t.Union[t.List[str], str]],
        ignore_app_dependencies_filepatterns: t.Optional[t.Union[t.List[str], str]],
        sdkconfig_defaults: t.Optional[str],
        include_skipped_apps: bool,
    ) -> t.List[App]:
        if default_build_targets:
            default_build_targets = to_list(default_build_targets)
            LOGGER.info('Overriding default build targets to %s', default_build_targets)
            FolderRule.DEFAULT_BUILD_TARGETS = default_build_targets

        if isinstance(build_system, str):
            # backwards compatible
            if build_system == 'cmake':
                build_system = CMakeApp
            elif build_system == 'make':
                build_system = MakeApp
            else:
                raise ValueError('Only Support "make" and "cmake"')
        app_cls = build_system

        # always set the manifest rootpath at the very beginning of find_apps in case ESP-IDF switches the branch.
        Manifest.ROOTPATH = to_absolute_path(manifest_rootpath or os.curdir)
        Manifest.CHECK_MANIFEST_RULES = check_manifest_rules

        if manifest_files:
            rules = set()
            for _manifest_file in to_list(manifest_files):
                LOGGER.debug('Loading manifest file: %s', _manifest_file)
                rules.update(Manifest.from_file(_manifest_file).rules)
            manifest = Manifest(rules)
            App.MANIFEST = manifest

        modified_components = to_list(modified_components)
        modified_files = to_list(modified_files)
        ignore_app_dependencies_filepatterns = to_list(ignore_app_dependencies_filepatterns)
        config_rules_str = to_list(config_rules_str)

        apps = []
        if target == 'all':
            targets = ALL_TARGETS
        else:
            targets = [target]

        for target in targets:
            for path in to_list(paths):
                path = path.strip()
                apps.extend(
                    _find_apps(
                        path,
                        target,
                        app_cls,
                        recursive,
                        exclude_list or [],
                        work_dir=work_dir,
                        build_dir=build_dir or 'build',
                        config_rules_str=config_rules_str,
                        build_log_filename=build_log_filename,
                        size_json_filename=size_json_filename,
                        check_warnings=check_warnings,
                        preserve=preserve,
                        manifest_rootpath=manifest_rootpath,
                        check_app_dependencies=self._check_app_dependency(
                            manifest_rootpath=manifest_rootpath,
                            modified_components=modified_components,
                            modified_files=modified_files,
                            ignore_app_dependencies_filepatterns=ignore_app_dependencies_filepatterns,
                        ),
                        modified_components=modified_components,
                        modified_files=modified_files,
                        sdkconfig_defaults_str=sdkconfig_defaults,
                        include_skipped_apps=include_skipped_apps,
                    )
                )

        LOGGER.info(f'Found {len(apps)} apps in total')

        return sorted(apps)

    @idf_build_apps_hookimpl
    def build_apps(
        self,
        apps: t.Union[t.List[App], App],
        build_verbose: bool,
        dry_run: bool,
        keep_going: bool,
        ignore_warning_strs: t.Optional[t.List[str]],
        ignore_warning_file: t.Optional[t.TextIO],
        copy_sdkconfig: bool,
        manifest_rootpath: t.Optional[str],
        modified_components: t.Optional[t.Union[t.List[str], str]],
        modified_files: t.Optional[t.Union[t.List[str], str]],
        ignore_app_dependencies_filepatterns: t.Optional[t.Union[t.List[str], str]],
        check_app_dependencies: t.Optional[bool],
        # BuildAppsArgs
        parallel_count: int,
        parallel_index: int,
        collect_size_info: t.Optional[str],
        collect_app_info: t.Optional[str],
        junitxml: t.Optional[str],
    ) -> int:
        apps = to_list(apps)
        modified_components = to_list(modified_components)
        modified_files = to_list(modified_files)
        ignore_app_dependencies_filepatterns = to_list(ignore_app_dependencies_filepatterns)

        test_suite = TestSuite('build_apps')

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

        build_apps_args = BuildAppsArgs(
            parallel_count=parallel_count,
            parallel_index=parallel_index,
            collect_size_info=collect_size_info,
            collect_app_info=collect_app_info,
            junitxml=junitxml,
        )
        for app in apps[start - 1 : stop]:  # we use 1-based
            app.build_apps_args = build_apps_args

        # cleanup collect files if exists at this early-stage
        for f in (build_apps_args.collect_app_info, build_apps_args.collect_size_info, build_apps_args.junitxml):
            if f and os.path.isfile(f):
                os.remove(f)
                LOGGER.debug('Remove existing collect file %s', f)
                os.mknod(f)

        exit_code = 0
        for i, app in enumerate(apps):
            index = i + 1  # we use 1-based
            if index < start or index > stop:
                continue

            # attrs
            app.dry_run = dry_run
            app.index = index
            app.verbose = build_verbose

            LOGGER.info('(%s/%s) Building app: %s', index, len(apps), app)

            app.build(
                manifest_rootpath=manifest_rootpath,
                modified_components=modified_components,
                modified_files=modified_files,
                check_app_dependencies=self._check_app_dependency(
                    manifest_rootpath, modified_components, modified_files, ignore_app_dependencies_filepatterns
                )
                if check_app_dependencies is None
                else check_app_dependencies,
            )
            test_suite.add_test_case(TestCase.from_app(app))

            if app.build_comment:
                LOGGER.info('%s (%s)', app.build_status.value, app.build_comment)
            else:
                LOGGER.info('%s', app.build_status.value)

            if build_apps_args.collect_app_info:
                with open(build_apps_args.collect_app_info, 'a') as fw:
                    fw.write(app.to_json() + '\n')
                LOGGER.debug('Recorded app info in %s', build_apps_args.collect_app_info)

            if copy_sdkconfig:
                try:
                    shutil.copy(
                        os.path.join(app.work_dir, 'sdkconfig'),
                        os.path.join(app.build_path, 'sdkconfig'),
                    )
                except Exception as e:
                    LOGGER.warning('Copy sdkconfig file from failed: %s', e)
                else:
                    LOGGER.debug('Copied sdkconfig file from %s to %s', app.work_dir, app.build_path)

            if app.build_status == BuildStatus.FAILED:
                if not keep_going:
                    return 1
                else:
                    exit_code = 1
            elif app.build_status == BuildStatus.SUCCESS:
                if build_apps_args.collect_size_info and app.size_json_path:
                    if os.path.isfile(app.size_json_path):
                        with open(build_apps_args.collect_size_info, 'a') as fw:
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
                        LOGGER.debug('Recorded size info file path in %s', build_apps_args.collect_size_info)

            LOGGER.info('')  # add one empty line for separating different builds

        if build_apps_args.junitxml:
            TestReport([test_suite], build_apps_args.junitxml).create_test_report()
            LOGGER.info('Generated junit report for build apps: %s', build_apps_args.junitxml)

        return exit_code
