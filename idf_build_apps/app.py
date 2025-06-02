# SPDX-FileCopyrightText: 2022-2025 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import copy
import functools
import json
import logging
import os
import re
import shutil
import sys
import typing as t
from datetime import datetime, timezone
from pathlib import (
    Path,
)

from packaging.version import (
    Version,
)
from pydantic import (
    Field,
    computed_field,
)

from . import (
    SESSION_ARGS,
)
from .constants import (
    DEFAULT_SDKCONFIG,
    IDF_PY,
    IDF_SIZE_PY,
    IDF_VERSION,
    IDF_VERSION_MAJOR,
    IDF_VERSION_MINOR,
    IDF_VERSION_PATCH,
    PREVIEW_TARGETS,
    PROJECT_DESCRIPTION_JSON,
    BuildStatus,
)
from .manifest.manifest import (
    DEFAULT_BUILD_TARGETS,
    Manifest,
)
from .utils import (
    BaseModel,
    BuildError,
    Literal,
    files_matches_patterns,
    find_first_match,
    rmdir,
    subprocess_run,
    to_absolute_path,
    to_list,
)

LOGGER = logging.getLogger(__name__)


class App(BaseModel):
    TARGET_PLACEHOLDER: t.ClassVar[str] = '@t'  # replace it with self.target
    WILDCARD_PLACEHOLDER: t.ClassVar[str] = '@w'  # replace it with the wildcard, usually the sdkconfig
    NAME_PLACEHOLDER: t.ClassVar[str] = '@n'  # replace it with self.name
    FULL_NAME_PLACEHOLDER: t.ClassVar[str] = '@f'  # replace it with escaped self.app_dir
    IDF_VERSION_PLACEHOLDER: t.ClassVar[str] = '@v'  # replace it with the IDF version
    INDEX_PLACEHOLDER: t.ClassVar[str] = '@i'  # replace it with the build index (while build_apps)

    SDKCONFIG_LINE_REGEX: t.ClassVar[t.Pattern] = re.compile(r'^([^=]+)=\"?([^\"\n]*)\"?\n*$')

    # could be assigned later, used for filtering out apps by supported_targets
    MANIFEST: t.ClassVar[t.Optional[Manifest]] = None
    # This RE will match GCC errors and many other fatal build errors and warnings as well
    LOG_ERROR_WARNING_REGEX: t.ClassVar[t.Pattern] = re.compile(r'(?:error|warning):', re.MULTILINE | re.IGNORECASE)
    # Log this many trailing lines from a failed build log, also
    LOG_DEBUG_LINES: t.ClassVar[int] = 25
    # IGNORE_WARNING_REGEX is a regex for warnings to be ignored. Could be assigned later
    IGNORE_WARNS_REGEXES: t.ClassVar[t.List[t.Pattern]] = []

    # ------------------
    # Instance variables
    # ------------------
    build_system: Literal['unknown'] = 'unknown'

    app_dir: str
    target: str
    sdkconfig_path: t.Optional[str] = None
    config_name: t.Optional[str] = None
    sdkconfig_defaults_str: t.Optional[str] = None
    # all parameters
    _kwargs: t.Dict[str, t.Any]

    # Attrs that support placeholders
    _work_dir: t.Optional[str] = None
    _build_dir: t.Optional[str] = None

    _build_log_filename: t.Optional[str] = None
    _size_json_filename: t.Optional[str] = None

    dry_run: bool = False
    verbose: bool = False
    check_warnings: bool = False
    preserve: bool = True
    copy_sdkconfig: bool = False

    # build_apps() related
    index: t.Optional[int] = None

    # build status related
    build_status: BuildStatus = BuildStatus.UNKNOWN
    build_comment: t.Optional[str] = None

    _build_duration: float = 0
    _build_timestamp: t.Optional[datetime] = None

    __EQ_IGNORE_FIELDS__ = [
        'build_comment',
    ]
    __EQ_TUNE_FIELDS__ = {
        'app_dir': lambda x: (os.path.realpath(os.path.expanduser(x))),
        'work_dir': lambda x: (os.path.realpath(os.path.expanduser(x))),
        'build_dir': lambda x: (os.path.realpath(os.path.expanduser(x))),
    }

    def __init__(
        self,
        app_dir: str,
        target: str,
        *,
        work_dir: t.Optional[str] = None,
        build_dir: str = 'build',
        build_log_filename: t.Optional[str] = None,
        size_json_filename: t.Optional[str] = None,
        **kwargs: t.Any,
    ) -> None:
        kwargs.update(
            {
                'app_dir': app_dir,
                'target': target,
            }
        )
        super().__init__(**kwargs)

        # These internal variables store the paths with environment variables and placeholders;
        # Public properties with similar names use the _expand method to get the actual paths.
        self._work_dir = work_dir or app_dir
        self._build_dir = build_dir or 'build'

        self._build_log_filename = build_log_filename
        self._size_json_filename = size_json_filename
        self._is_build_log_path_temp = not bool(build_log_filename)

        # pass all parameters to initialize hook method
        kwargs.update(
            {
                'work_dir': self._work_dir,
                'build_dir': self._build_dir,
                'build_log_filename': build_log_filename,
                'size_json_filename': size_json_filename,
            }
        )
        self._kwargs = kwargs
        self._initialize_hook(**kwargs)

        # private attrs, won't be dumped to json
        self._checked_should_build = False

        self._sdkconfig_files, self._sdkconfig_files_defined_target = self._process_sdkconfig_files()

    @classmethod
    def from_another(cls, other: 'App', **kwargs) -> 'App':
        """Init New App from another, with different parameters.

        eg: new_app = [Cmake]App.from_another(app, config='debug')
        """
        new_kwargs = copy.deepcopy(other._kwargs)
        new_kwargs.update(kwargs)
        return cls(**new_kwargs)

    def _initialize_hook(self, **kwargs):
        """
        Called after variables initialized, before actions such as creating logger.
        """
        pass

    def __str__(self):
        default_fmt = '({}) App {}, target {}, sdkconfig {}, build in {}'
        default_args = [
            self.build_system,
            self.app_dir,
            self.target,
            self.sdkconfig_path or '(default)',
            self.build_path,
        ]

        if self.build_status in (BuildStatus.UNKNOWN, BuildStatus.SHOULD_BE_BUILT):
            return default_fmt.format(*default_args)

        default_fmt += ', {} in {}s'
        default_args += [
            self.build_status.value,
            self._build_duration,
        ]

        if self.build_comment:
            default_fmt += ': {}'
            default_args.append(self.build_comment)

        return default_fmt.format(*default_args)

    @property
    def sdkconfig_defaults_candidates(self) -> t.List[str]:
        if self.sdkconfig_defaults_str is not None:
            return self.sdkconfig_defaults_str.split(';')

        if os.getenv('SDKCONFIG_DEFAULTS', None) is not None:
            return os.getenv('SDKCONFIG_DEFAULTS', '').split(';')

        return [DEFAULT_SDKCONFIG]

    @t.overload
    def _expand(self, path: None) -> None: ...

    @t.overload
    def _expand(self, path: str) -> str: ...

    def _expand(self, path):
        """
        Internal method, expands any of the placeholders in {app,work,build} paths.
        """
        if not path:
            return path

        if self.index is not None:
            path = path.replace(self.INDEX_PLACEHOLDER, str(self.index))
        path = path.replace(
            self.IDF_VERSION_PLACEHOLDER, f'{IDF_VERSION_MAJOR}_{IDF_VERSION_MINOR}_{IDF_VERSION_PATCH}'
        )
        path = path.replace(self.TARGET_PLACEHOLDER, self.target)
        path = path.replace(self.NAME_PLACEHOLDER, self.name)
        if self.FULL_NAME_PLACEHOLDER in path:  # to avoid recursion to the call to app_dir in the next line:
            path = path.replace(self.FULL_NAME_PLACEHOLDER, self.app_dir.replace(os.path.sep, '_'))
        wildcard_pos = path.find(self.WILDCARD_PLACEHOLDER)
        if wildcard_pos != -1:
            if self.config_name:
                # if config name is defined, put it in place of the placeholder
                path = path.replace(self.WILDCARD_PLACEHOLDER, self.config_name)
            else:
                # otherwise, remove the placeholder and one character on the left
                # (which is usually an underscore, dash, or other delimiter)
                left_of_wildcard = max(0, wildcard_pos - 1)
                right_of_wildcard = wildcard_pos + len(self.WILDCARD_PLACEHOLDER)
                path = path[0:left_of_wildcard] + path[right_of_wildcard:]
        path = os.path.expandvars(path)
        return path

    @property
    def name(self) -> str:
        base_name = os.path.basename(self.app_dir)
        # '.' for relative path like '.'
        # '' for path endswith '/'
        if base_name in ['.', '']:
            return os.path.basename(os.path.abspath(self.app_dir))
        return base_name

    @computed_field  # type: ignore
    @property
    def work_dir(self) -> str:
        """
        :return: directory where the app should be copied to, prior to the build.
        """
        return self._expand(self._work_dir)  # type: ignore

    @computed_field  # type: ignore
    @property
    def build_dir(self) -> str:
        """
        :return: build directory, either relative to the work directory (if relative path is used) or absolute path.
        """
        return self._expand(self._build_dir)  # type: ignore

    @property
    def build_path(self) -> str:
        if os.path.isabs(self.build_dir):
            return self.build_dir

        return os.path.join(self.work_dir, self.build_dir)

    @computed_field  # type: ignore
    @property
    def build_log_filename(self) -> t.Optional[str]:
        return self._expand(self._build_log_filename)

    @property
    def build_log_path(self) -> str:
        if self.build_log_filename:
            return os.path.join(self.build_path, self.build_log_filename)

        # use a temp file if build log path is not specified
        return os.path.join(self.build_path, '.temp.build.log')

    @computed_field  # type: ignore
    @property
    def size_json_filename(self) -> t.Optional[str]:
        if self.target == 'linux':
            # esp-idf-size does not support linux target
            return None

        return self._expand(self._size_json_filename)

    @property
    def size_json_path(self) -> t.Optional[str]:
        if self.size_json_filename:
            return os.path.join(self.build_path, self.size_json_filename)

        return None

    def _process_sdkconfig_files(self) -> t.Tuple[t.List[str], t.Optional[str]]:
        """
        Expand environment variables in default sdkconfig files and remove some CI related settings.
        """
        real_sdkconfig_files: t.List[str] = []
        sdkconfig_files_defined_target: t.Optional[str] = None

        # put the expanded variable files in a temporary directory
        # will remove if the content is the same as the original one
        expanded_dir = os.path.join(self.work_dir, 'expanded_sdkconfig_files', os.path.basename(self.build_dir))
        if not os.path.isdir(expanded_dir):
            os.makedirs(expanded_dir)

        for f in self.sdkconfig_defaults_candidates + ([self.sdkconfig_path] if self.sdkconfig_path else []):
            # use filepath if abs/rel already point to itself
            if not os.path.isfile(f):
                # find it in the app_dir
                LOGGER.debug('sdkconfig file %s not found, checking under app_dir...', f)
                f = os.path.join(self.app_dir, f)
                if not os.path.isfile(f):
                    LOGGER.debug('sdkconfig file %s not found, skipping...', f)
                    continue

            expanded_fp = os.path.join(expanded_dir, os.path.basename(f))
            with open(f) as fr:
                with open(expanded_fp, 'w') as fw:
                    for line in fr:
                        line = os.path.expandvars(line)

                        m = self.SDKCONFIG_LINE_REGEX.match(line)
                        if m:
                            key = m.group(1)
                            if key == 'CONFIG_IDF_TARGET':
                                sdkconfig_files_defined_target = m.group(2)

                            if isinstance(self, CMakeApp):
                                if key in self.SDKCONFIG_TEST_OPTS:
                                    self.cmake_vars[key] = m.group(2)
                                    continue

                                if key in self.SDKCONFIG_IGNORE_OPTS:
                                    continue

                        fw.write(line)

            with open(f) as fr:
                with open(expanded_fp) as new_fr:
                    if fr.read() == new_fr.read():
                        LOGGER.debug('Use sdkconfig file %s', f)
                        try:
                            os.unlink(expanded_fp)
                        except OSError:
                            LOGGER.debug('Failed to remove file %s', expanded_fp)
                        real_sdkconfig_files.append(f)
                    else:
                        LOGGER.debug('Expand sdkconfig file %s to %s', f, expanded_fp)
                        real_sdkconfig_files.append(expanded_fp)
                        # copy the related target-specific sdkconfig files
                        par_dir = os.path.abspath(os.path.join(f, '..'))
                        for target_specific_file in (
                            os.path.join(par_dir, str(p))
                            for p in Path(par_dir).glob(os.path.basename(f) + f'.{self.target}')
                        ):
                            LOGGER.debug(
                                'Copy target-specific sdkconfig file %s to %s', target_specific_file, expanded_dir
                            )
                            shutil.copy(target_specific_file, expanded_dir)

        # remove if expanded folder is empty
        try:
            os.rmdir(expanded_dir)
        except OSError:
            pass

        try:
            os.rmdir(os.path.join(self.work_dir, 'expanded_sdkconfig_files'))
        except OSError:
            pass

        if SESSION_ARGS.override_sdkconfig_file_path:
            real_sdkconfig_files.append(SESSION_ARGS.override_sdkconfig_file_path)
            if 'CONFIG_IDF_TARGET' in SESSION_ARGS.override_sdkconfig_items:
                sdkconfig_files_defined_target = SESSION_ARGS.override_sdkconfig_items['CONFIG_IDF_TARGET']

        return real_sdkconfig_files, sdkconfig_files_defined_target

    @property
    def sdkconfig_files_defined_idf_target(self) -> t.Optional[str]:
        return self._sdkconfig_files_defined_target

    @property
    def sdkconfig_files(self) -> t.List[str]:
        return [os.path.abspath(file) for file in self._sdkconfig_files]

    @property
    def depends_components(self) -> t.List[str]:
        if self.MANIFEST:
            return self.MANIFEST.depends_components(
                self.app_dir, self.sdkconfig_files_defined_idf_target, self.config_name
            )

        return []

    @property
    def depends_filepatterns(self) -> t.List[str]:
        if self.MANIFEST:
            return self.MANIFEST.depends_filepatterns(
                self.app_dir, self.sdkconfig_files_defined_idf_target, self.config_name
            )

        return []

    @property
    def supported_targets(self) -> t.List[str]:
        if self.MANIFEST:
            return self.MANIFEST.enable_build_targets(
                self.app_dir, self.sdkconfig_files_defined_idf_target, self.config_name
            )

        if self.sdkconfig_files_defined_idf_target:
            return [self.sdkconfig_files_defined_idf_target]

        return DEFAULT_BUILD_TARGETS.get()

    @property
    def verified_targets(self) -> t.List[str]:
        if self.MANIFEST:
            return self.MANIFEST.enable_test_targets(
                self.app_dir, self.sdkconfig_files_defined_idf_target, self.config_name
            )

        return []

    def record_build_duration(func):
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            self._build_timestamp = datetime.now(timezone.utc)
            try:
                return func(self, *args, **kwargs)
            finally:
                self._build_duration = (datetime.now(timezone.utc) - self._build_timestamp).total_seconds()

        return wrapper

    def _pre_build(self) -> None:
        if self.build_status == BuildStatus.SKIPPED:
            return

        if self.work_dir != self.app_dir:
            if os.path.exists(self.work_dir):
                LOGGER.debug('Removed existing work dir: %s', self.work_dir)
                if not self.dry_run:
                    shutil.rmtree(self.work_dir)

            LOGGER.debug('Copied app from %s to %s', self.app_dir, self.work_dir)
            if not self.dry_run:
                # if the new directory inside the original directory,
                # make sure not to go into recursion.
                ignore = shutil.ignore_patterns(
                    os.path.basename(self.work_dir),
                    # also ignore files which may be present in the work directory
                    'build',
                    'sdkconfig',
                )

                shutil.copytree(self.app_dir, self.work_dir, ignore=ignore, symlinks=True)

        if os.path.exists(self.build_path):
            LOGGER.debug('Removed existing build dir: %s', self.build_path)
            if not self.dry_run:
                shutil.rmtree(self.build_path)

        if not self.dry_run:
            os.makedirs(self.build_path, exist_ok=True)

        sdkconfig_file = os.path.join(self.work_dir, 'sdkconfig')
        if os.path.exists(sdkconfig_file):
            LOGGER.debug('Removed existing sdkconfig file: %s', sdkconfig_file)
            if not self.dry_run:
                os.unlink(sdkconfig_file)

        if os.path.isfile(self.build_log_path):
            LOGGER.debug('Removed existing build log file: %s', self.build_log_path)
            if not self.dry_run:
                os.unlink(self.build_log_path)
        elif not self.dry_run:
            os.makedirs(os.path.dirname(self.build_log_path), exist_ok=True)
        LOGGER.info('Writing build log to %s', self.build_log_path)

        if self.dry_run:
            self.build_status = BuildStatus.SKIPPED
            self.build_comment = 'dry run'
            return

    @record_build_duration  # type: ignore
    def build(
        self,
        *,
        manifest_rootpath: t.Optional[str] = None,
        modified_components: t.Union[t.List[str], str, None] = None,
        modified_files: t.Union[t.List[str], str, None] = None,
        check_app_dependencies: bool = False,
    ) -> None:
        if self.build_status not in (
            BuildStatus.UNKNOWN,
            BuildStatus.SHOULD_BE_BUILT,
        ):
            self.build_comment = f'Build {self.build_status.value}. Skipping...'
            return

        # real build starts here
        self._pre_build()

        try:
            self._build(
                manifest_rootpath=manifest_rootpath,
                modified_components=to_list(modified_components),
                modified_files=to_list(modified_files),
                check_app_dependencies=check_app_dependencies,
            )
        except BuildError as e:
            self.build_status = BuildStatus.FAILED
            self.build_comment = str(e)

        self._post_build()

        self._finalize()

    def _post_build(self) -> None:
        """Post build actions for failed/success builds"""
        if self.build_status not in (
            BuildStatus.FAILED,
            BuildStatus.SUCCESS,
        ):
            return

        # both status applied
        if self.copy_sdkconfig:
            try:
                shutil.copy(
                    os.path.join(self.work_dir, 'sdkconfig'),
                    os.path.join(self.build_path, 'sdkconfig'),
                )
            except Exception as e:
                LOGGER.warning('Copy sdkconfig file from failed: %s', e)
            else:
                LOGGER.debug('Copied sdkconfig file from %s to %s', self.work_dir, self.build_path)

        # for originally success builds generate size.json if enabled
        #
        # for the rest of the actions, we need to check if there's further build warnings
        # to tell if this build is successful or not
        if self.build_status == BuildStatus.SUCCESS:
            self.write_size_json()

        if not os.path.isfile(self.build_log_path):
            LOGGER.warning(f'{self.build_log_path} does not exist. Skipping post build actions...')
            return

        # check warnings
        has_unignored_warning = False
        with open(self.build_log_path) as fr:
            lines = [line.rstrip() for line in fr if line.rstrip()]
            for line in lines:
                is_error_or_warning, ignored = self.is_error_or_warning(line)
                if is_error_or_warning:
                    if ignored:
                        LOGGER.info('[Ignored warning] %s', line)
                    else:
                        LOGGER.warning('%s', line)
                        has_unignored_warning = True

        # for failed builds, print last few lines to help debug
        if self.build_status == BuildStatus.FAILED:
            # print last few lines to help debug
            LOGGER.error(
                'Last %s lines from the build log "%s":',
                self.LOG_DEBUG_LINES,
                self.build_log_path,
            )
            for line in lines[-self.LOG_DEBUG_LINES :]:
                LOGGER.error('%s', line)
        # correct build status for originally successful builds
        elif self.build_status == BuildStatus.SUCCESS:
            if self.check_warnings and has_unignored_warning:
                self.build_status = BuildStatus.FAILED
                self.build_comment = 'build succeeded with warnings'
            elif has_unignored_warning:
                self.build_comment = 'build succeeded with warnings'

    def _finalize(self) -> None:
        """
        Actions for real success builds
        """
        if self.build_status != BuildStatus.SUCCESS:
            return

        # remove temp log file
        if self._is_build_log_path_temp:
            os.unlink(self.build_log_path)
            LOGGER.debug('Removed success build temporary log file: %s', self.build_log_path)

        # Cleanup build directory if not preserving
        if not self.preserve:
            exclude_list = []
            if self.size_json_path:
                exclude_list.append(os.path.basename(self.size_json_path))
            exclude_list.append(os.path.basename(self.build_log_path))

            rmdir(
                self.build_path,
                exclude_file_patterns=exclude_list,
            )
            LOGGER.debug('Removed built binaries under: %s', self.build_path)

    def _build(
        self,
        *,
        manifest_rootpath: t.Optional[str] = None,
        modified_components: t.Optional[t.List[str]] = None,
        modified_files: t.Optional[t.List[str]] = None,
        check_app_dependencies: bool = False,
    ) -> None:
        pass

    def _write_size_json(self) -> None:
        if not self.size_json_path:
            return

        map_file = find_first_match('*.map', self.build_path)
        if not map_file:
            LOGGER.warning(
                '.map file not found. Cannot write size json to file: %s',
                self.size_json_path,
            )
            return

        if IDF_VERSION >= Version('4.1'):
            subprocess_run(
                [
                    sys.executable,
                    str(IDF_SIZE_PY),
                ]
                + (['--json'] if IDF_VERSION < Version('5.1') else ['--format', 'json'])
                + [
                    '-o',
                    self.size_json_path,
                    map_file,
                ],
                check=True,
            )
        else:
            with open(self.size_json_path, 'w') as fw:
                subprocess_run(
                    (
                        [
                            sys.executable,
                            str(IDF_SIZE_PY),
                            '--json',
                            map_file,
                        ]
                    ),
                    log_terminal=False,
                    log_fs=fw,
                    check=True,
                )

        LOGGER.debug('Generated size info to %s', self.size_json_path)

    def write_size_json(self) -> None:
        if self.target in PREVIEW_TARGETS:
            # targets in preview may not yet have support in esp-idf-size
            LOGGER.info('Skipping generation of size json for target %s as it is in preview.', self.target)
            return

        try:
            self._write_size_json()
        except Exception as e:
            LOGGER.warning('Failed to generate size json: %s', e)

    def to_json(self) -> str:
        return self.model_dump_json()

    def is_error_or_warning(self, line: str) -> t.Tuple[bool, bool]:
        if not self.LOG_ERROR_WARNING_REGEX.search(line):
            return False, False

        is_ignored = False
        for ignored in self.IGNORE_WARNS_REGEXES:
            if re.search(ignored, line):
                is_ignored = True
                break

        return True, is_ignored

    @classmethod
    def is_app(cls, path: str) -> bool:
        raise NotImplementedError('Please implement this function in sub classes')

    def is_modified(self, modified_files: t.Optional[t.List[str]]) -> bool:
        _app_dir_fullpath = to_absolute_path(self.app_dir)
        if modified_files:
            for f in modified_files:
                _f_fullpath = to_absolute_path(f)
                if os.path.basename(_f_fullpath).endswith('.md'):
                    continue

                if _f_fullpath.startswith(_app_dir_fullpath):
                    return True

        return False

    def check_should_build(
        self,
        *,
        manifest_rootpath: t.Optional[str] = None,
        modified_manifest_rules_folders: t.Optional[t.Set[str]] = None,
        check_app_dependencies: bool = False,
        modified_components: t.Optional[t.List[str]] = None,
        modified_files: t.Optional[t.List[str]] = None,
    ) -> None:
        if self.build_status != BuildStatus.UNKNOWN:
            return

        if not check_app_dependencies:
            self.build_status = BuildStatus.SHOULD_BE_BUILT
            self._checked_should_build = True
            return

        if (
            self.MANIFEST
            and modified_manifest_rules_folders
            and self.MANIFEST.most_suitable_rule(self.app_dir).folder in modified_manifest_rules_folders
        ):
            self.build_status = BuildStatus.SHOULD_BE_BUILT
            self.build_comment = 'current build modifies the related manifest rules'
            self._checked_should_build = True
            return

        if self.is_modified(modified_files):
            self.build_status = BuildStatus.SHOULD_BE_BUILT
            self.build_comment = 'current build modifies this app'
            self._checked_should_build = True
            return

        # if didn't modify any components, and no `depends_filepatterns` defined, skip
        if modified_components == [] and not self.depends_filepatterns:
            self.build_status = BuildStatus.SKIPPED
            self.build_comment = 'current build does not modify any components'
            self._checked_should_build = True
            return

        # if no special rules defined, we left it unknown and decide with idf.py reconfigure
        if not self.depends_components and not self.depends_filepatterns:
            # keep unknown
            self._checked_should_build = True
            self.build_comment = 'no special rules defined, run idf.py reconfigure to decide'
            return

        # check app dependencies
        modified_components = to_list(modified_components)
        modified_files = to_list(modified_files)

        # depends components?
        if self.depends_components and modified_components is not None:
            if set(self.depends_components).intersection(set(modified_components)):
                self._checked_should_build = True
                self.build_status = BuildStatus.SHOULD_BE_BUILT
                self.build_comment = (
                    f'Requires components: {", ".join(self.depends_components)}. '
                    f'Modified components: {", ".join(modified_components)}'
                )
                return

        # or depends file patterns?
        if self.depends_filepatterns and modified_files is not None:
            if files_matches_patterns(modified_files, self.depends_filepatterns, manifest_rootpath):
                self._checked_should_build = True
                self.build_status = BuildStatus.SHOULD_BE_BUILT
                self.build_comment = (
                    f'Requires file patterns: {", ".join(self.depends_filepatterns)}. '
                    f'Modified files: {", ".join(modified_files)}'
                )
                return

        # special rules defined, but not matched
        self.build_status = BuildStatus.SKIPPED
        self.build_comment = 'current build does not modify any components or files required by this app'
        self._checked_should_build = True


class MakeApp(App):
    MAKE_PROJECT_LINE: t.ClassVar[str] = r'include $(IDF_PATH)/make/project.mk'

    build_system: Literal['make'] = 'make'  # type: ignore

    @property
    def supported_targets(self) -> t.List[str]:
        if self.MANIFEST:
            return self.MANIFEST.enable_build_targets(
                self.app_dir, self.sdkconfig_files_defined_idf_target, self.config_name
            )

        if self.sdkconfig_files_defined_idf_target:
            return [self.sdkconfig_files_defined_idf_target]

        return ['esp8266', *DEFAULT_BUILD_TARGETS.get()]

    def _build(
        self,
        *,
        manifest_rootpath: t.Optional[str] = None,
        modified_components: t.Optional[t.List[str]] = None,
        modified_files: t.Optional[t.List[str]] = None,
        check_app_dependencies: bool = False,
    ) -> None:
        super()._build(
            manifest_rootpath=manifest_rootpath,
            modified_components=modified_components,
            modified_files=modified_files,
            check_app_dependencies=check_app_dependencies,
        )

        # additional env variables
        additional_env_dict = {
            'IDF_TARGET': self.target,
            'BUILD_DIR_BASE': self.build_path,
        }

        commands = [
            # generate sdkconfig
            ['make', 'defconfig'],
            # build
            ['make', f'-j{os.cpu_count() or 1}'],
        ]

        for cmd in commands:
            subprocess_run(
                cmd,
                log_terminal=self._is_build_log_path_temp,
                log_fs=self.build_log_path,
                check=True,
                additional_env_dict=additional_env_dict,
                cwd=self.work_dir,
            )

        self.build_status = BuildStatus.SUCCESS

    @classmethod
    def is_app(cls, path: str) -> bool:
        makefile_path = os.path.join(path, 'Makefile')
        if not os.path.exists(makefile_path):
            return False

        with open(makefile_path) as makefile:
            makefile_content = makefile.read()

        if cls.MAKE_PROJECT_LINE not in makefile_content:
            return False

        return True


class CMakeApp(App):
    # If these keys are present in sdkconfig.defaults, they will be extracted and passed to CMake
    SDKCONFIG_TEST_OPTS: t.ClassVar[t.List[str]] = [
        'EXCLUDE_COMPONENTS',
        'TEST_EXCLUDE_COMPONENTS',
        'TEST_COMPONENTS',
    ]

    # These keys in sdkconfig.defaults are not propagated to the final sdkconfig file:
    SDKCONFIG_IGNORE_OPTS: t.ClassVar[t.List[str]] = ['TEST_GROUPS']

    # While ESP-IDF component CMakeLists files can be identified by the presence of 'idf_component_register' string,
    # there is no equivalent for the project CMakeLists files. This seems to be the best option...
    CMAKE_PROJECT_LINE: t.ClassVar[str] = r'include($ENV{IDF_PATH}/tools/cmake/project.cmake)'

    build_system: Literal['cmake'] = 'cmake'  # type: ignore

    cmake_vars: t.Dict[str, str] = {}

    def _build(
        self,
        *,
        manifest_rootpath: t.Optional[str] = None,
        modified_components: t.Optional[t.List[str]] = None,
        modified_files: t.Optional[t.List[str]] = None,
        check_app_dependencies: bool = False,
    ) -> None:
        super()._build(
            manifest_rootpath=manifest_rootpath,
            modified_components=modified_components,
            modified_files=modified_files,
            check_app_dependencies=check_app_dependencies,
        )

        if not self._checked_should_build:
            self.check_should_build(
                manifest_rootpath=manifest_rootpath,
                modified_components=modified_components,
                modified_files=modified_files,
                check_app_dependencies=check_app_dependencies,
            )

        # additional env variables
        # IDF_TARGET to bypass the idf.py build check
        additional_env_dict = {
            'IDF_TARGET': self.target,
        }

        # check if this app depends on components according to the project_description.json 'build_component' field.
        # the file is generated by `idf.py reconfigure`.
        common_args = [
            sys.executable,
            str(IDF_PY),
            '-B',
            self.build_path,
            '-C',
            self.work_dir,
            f'-DIDF_TARGET={self.target}',
            # set to ";" to disable `default` when no such variable
            '-DSDKCONFIG_DEFAULTS={}'.format(';'.join(self.sdkconfig_files) if self.sdkconfig_files else ';'),
        ]

        if self.build_status == BuildStatus.UNKNOWN and modified_components is not None and check_app_dependencies:
            subprocess_run(
                [*common_args, 'reconfigure'],
                log_terminal=self._is_build_log_path_temp,
                log_fs=self.build_log_path,
                check=True,
                additional_env_dict=additional_env_dict,
            )
            LOGGER.debug('generated project_description.json to check app dependencies')

            with open(os.path.join(self.build_path, PROJECT_DESCRIPTION_JSON)) as fr:
                build_components = {item for item in json.load(fr)['build_components'] if item}

            if not set(modified_components).intersection(set(build_components)):
                self.build_status = BuildStatus.SKIPPED
                self.build_comment = (
                    f'app {self.app_dir} depends components: {build_components}, '
                    f'while current build modified components: {modified_components}'
                )
                return

        if self.build_status == BuildStatus.SKIPPED:
            return

        # idf.py build
        if self.cmake_vars:
            for key, val in self.cmake_vars.items():
                common_args.append(f'-D{key}={val}')
            if 'TEST_EXCLUDE_COMPONENTS' in self.cmake_vars and 'TEST_COMPONENTS' not in self.cmake_vars:
                common_args.append('-DTESTS_ALL=1')
            if 'CONFIG_APP_BUILD_BOOTLOADER' in self.cmake_vars:
                # In case if secure_boot is enabled then for bootloader build need to add `bootloader` cmd
                common_args.append('bootloader')
        common_args.append('build')
        if self.verbose:
            common_args.append('-v')

        subprocess_run(
            common_args,
            log_terminal=self._is_build_log_path_temp,
            log_fs=self.build_log_path,
            check=True,
            additional_env_dict=additional_env_dict,
        )

        self.build_status = BuildStatus.SUCCESS

    @classmethod
    def is_app(cls, path: str) -> bool:
        cmakelists_path = os.path.join(path, 'CMakeLists.txt')
        if not os.path.exists(cmakelists_path):
            return False

        with open(cmakelists_path) as fr:
            cmakelists_file_content = fr.read()

        if not cmakelists_file_content:
            return False

        if cls.CMAKE_PROJECT_LINE not in cmakelists_file_content:
            return False

        return True


class AppDeserializer(BaseModel):
    app: t.Union[App, CMakeApp, MakeApp] = Field(discriminator='build_system')

    @classmethod
    def from_json(cls, json_data: t.Union[str, bytes, bytearray]) -> App:
        json_dict = json.loads(json_data.strip())
        return cls.model_validate({'app': json_dict}).app

    @classmethod
    def from_json_list(cls, json_list: t.Sequence[t.Union[str, bytes, bytearray]]) -> t.List[App]:
        apps = []
        for app_json in json_list:
            apps.append(cls.from_json(app_json))

        return apps
