# SPDX-FileCopyrightText: 2022-2023 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import enum
import json
import os
import re
import shutil
import sys
import tempfile
import typing as t
from abc import (
    abstractmethod,
)
from copy import (
    deepcopy,
)
from functools import (
    cached_property,
)
from pathlib import (
    Path,
)
from typing import (
    ClassVar,
)

from packaging.version import (
    Version,
)
from pydantic import (
    BaseModel,
    ConfigDict,
    computed_field,
)

from . import (
    CONFIG,
    LOGGER,
)
from .constants import (
    DEFAULT_BUILD_DIR,
    IDF_PY,
    IDF_SIZE_PY,
    IDF_VERSION,
    IDF_VERSION_MAJOR,
    IDF_VERSION_MINOR,
    IDF_VERSION_PATCH,
    PROJECT_DESCRIPTION_JSON,
)
from .utils import (
    BuildError,
    find_first_match,
    rmdir,
    subprocess_run,
    to_absolute_path,
)


class BuildStatus(enum.StrEnum):
    UNKNOWN = 'unknown'
    NOT_DECIDED = 'not_decided'
    SHOULD_BE_BUILT = 'should be built'
    SKIPPED = 'skipped'
    FAILED = 'build failed'
    SUCCESS = 'build success'


class App(BaseModel):
    model_config = ConfigDict(
        validate_assignment=True,
    )

    BUILD_SYSTEM: ClassVar[str] = 'unknown'

    # Placeholders
    TARGET_PLACEHOLDER: ClassVar[str] = '@t'  # replace it with self.target
    WILDCARD_PLACEHOLDER: ClassVar[str] = '@w'  # replace it with the wildcard, usually the CONFIG_NAME
    NAME_PLACEHOLDER: ClassVar[str] = '@n'  # replace it with self.name
    FULL_NAME_PLACEHOLDER: ClassVar[str] = '@f'  # replace it with escaped self.app_dir
    INDEX_PLACEHOLDER: ClassVar[str] = '@i'  # replace it with the build index
    PARALLEL_INDEX_PLACEHOLDER: ClassVar[str] = '@p'  # replace it with the parallel index
    IDF_VERSION_PLACEHOLDER: ClassVar[str] = '@v'  # replace it with the IDF version

    # The regex to match the sdkconfig settings lines
    SDKCONFIG_LINE_REGEX: ClassVar[t.Pattern] = re.compile(r"^([^=]+)=\"?([^\"\n]*)\"?\n*$")
    # The regex to match the build log for errors and warnings
    LOG_ERROR_WARNING_REGEX: ClassVar[t.Pattern] = re.compile(r'(?:error|warning):', re.MULTILINE | re.IGNORECASE)
    # The number of lines to show from the build log when an error occurs
    LOG_DEBUG_LINES: ClassVar[int] = 25
    # A list of regexes to ignore warnings from the build log
    IGNORE_WARNS_REGEXES: ClassVar[t.List[t.Pattern]] = []

    # ------------------
    # Instance variables
    # ------------------
    # Attrs that support placeholders
    _work_dir: t.Optional[str] = None
    _build_dir: t.Optional[str] = None

    _build_log_path: t.Optional[str] = None
    _size_json_path: t.Optional[str] = None

    _collect_app_info: t.Optional[str] = None
    _collect_size_info: t.Optional[str] = None

    # Others
    app_dir: str
    target: str
    sdkconfig_path: t.Optional[str] = None
    config_name: t.Optional[str] = None

    # Build related
    dry_run: bool = False
    index: t.Union[int, None] = None
    verbose: bool = False
    check_warnings: bool = False
    preserve: bool = True
    parallel_index: int = 1
    parallel_count: int = 1

    skipped_reason: t.Optional[str] = None
    failed_reason: t.Optional[str] = None

    def __init__(
        self,
        *,
        work_dir: t.Optional[str] = None,
        build_dir: t.Optional[str] = None,
        build_log_path: t.Optional[str] = None,
        size_json_path: t.Optional[str] = None,
        collect_app_info: t.Optional[str] = None,
        collect_size_info: t.Optional[str] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)  # validate the model
        self._work_dir = work_dir or kwargs['app_dir']
        self._build_dir = build_dir or DEFAULT_BUILD_DIR
        self._build_log_path = build_log_path
        self._size_json_path = size_json_path
        self._collect_app_info = collect_app_info
        self._collect_size_info = collect_size_info

        self._sdkconfig_files_defined_idf_target = None  # will be set by `self.sdkconfig_files`
        self._build_status: BuildStatus = BuildStatus.UNKNOWN

        self.sdkconfig_files  # noqa  # call it here

    def __lt__(self, other):
        if isinstance(other, App):
            for k in self.model_dump():
                if getattr(self, k) != getattr(other, k):
                    return getattr(self, k) < getattr(other, k)
                else:
                    continue

        return NotImplemented

    def __eq__(self, other):
        if isinstance(other, App):
            # build_status is not calculated
            self_dict = self.model_dump()
            other_dict = other.model_dump()
            for k in ['build_status']:
                self_dict.pop(k)
                other_dict.pop(k)

            return self_dict == other_dict

        return NotImplemented

    def __hash__(self):
        hash_list = []
        for v in self.__dict__.values():
            if isinstance(v, list):
                hash_list.append(tuple(v))
            elif isinstance(v, dict):
                hash_list.append(tuple(v.items()))
            else:
                hash_list.append(v)

        return hash((type(self),) + tuple(hash_list))

    def expand_placeholders(self, s: t.Optional[str]) -> t.Optional[str]:
        """
        Expand the placeholders and system variables in a string.

        :param s: a string that may contain placeholders
        :return: a string with placeholders expanded
        """
        if not s:
            return s

        if self.index is not None:
            s = s.replace(self.INDEX_PLACEHOLDER, str(self.index))

        s = s.replace(self.PARALLEL_INDEX_PLACEHOLDER, str(self.parallel_index))

        s = s.replace(self.IDF_VERSION_PLACEHOLDER, f'{IDF_VERSION_MAJOR}_{IDF_VERSION_MINOR}_{IDF_VERSION_PATCH}')

        s = s.replace(self.TARGET_PLACEHOLDER, self.target)

        s = s.replace(self.NAME_PLACEHOLDER, self.name)

        s = s.replace(self.FULL_NAME_PLACEHOLDER, self.app_dir.replace(os.path.sep, '_'))

        wildcard_pos = s.find(self.WILDCARD_PLACEHOLDER)
        if wildcard_pos != -1:
            if self.config_name:
                # if config name is defined, put it in place of the placeholder
                s = s.replace(self.WILDCARD_PLACEHOLDER, self.config_name)
            else:
                # otherwise, remove the placeholder and one character on the left
                # (which is usually an underscore, dash, or other delimiter)
                left_of_wildcard = max(0, wildcard_pos - 1)
                right_of_wildcard = wildcard_pos + len(self.WILDCARD_PLACEHOLDER)
                s = s[0:left_of_wildcard] + s[right_of_wildcard:]

        return os.path.expandvars(s)

    ####################################
    # Attrs that supports placeholders #
    ####################################
    @computed_field
    @property
    def work_dir(self) -> str:
        return self.expand_placeholders(self._work_dir)

    @computed_field
    @property
    def build_dir(self) -> str:
        return self.expand_placeholders(self._build_dir)

    @computed_field
    @property
    def build_log_path(self) -> t.Optional[str]:
        return self.expand_placeholders(self._build_log_path)

    @computed_field
    @property
    def size_json_path(self) -> t.Optional[str]:
        return self.expand_placeholders(self._size_json_path)

    @size_json_path.setter
    def size_json_path(self, v: t.Optional[str]):
        self._size_json_path = v

    @computed_field
    @property
    def collect_app_info(self) -> t.Optional[str]:
        return self.expand_placeholders(self._collect_app_info)

    @computed_field
    @property
    def collect_size_info(self) -> t.Optional[str]:
        return self.expand_placeholders(self._collect_size_info)

    @computed_field
    @property
    def sdkconfig_files_defined_idf_target(self) -> t.Optional[str]:
        return self._sdkconfig_files_defined_idf_target

    @computed_field
    @cached_property  # calculated once
    def sdkconfig_files(self) -> t.List[str]:
        """
        Get all sdkconfig files that will be used to build the app.

        .. note::

            1. The order of the files is important, the later ones will override the previous ones.
            2. The environment variables inside the sdkconfig files are expanded.
        """
        res = []

        expanded_dir = os.path.join(self.work_dir, 'expanded_sdkconfig_files', os.path.basename(self.build_dir))
        if not os.path.isdir(expanded_dir):
            os.makedirs(expanded_dir)

        for f in CONFIG.default_sdkconfig_defaults + ([self.sdkconfig_path] if self.sdkconfig_path else []):
            if not os.path.isabs(f):
                f = os.path.join(self.work_dir, f)

            if not os.path.isfile(f):
                LOGGER.debug('=> sdkconfig file %s not exists, skipping...', f)
                continue

            expanded_fp = os.path.join(expanded_dir, os.path.basename(f))
            with open(f) as fr:
                with open(expanded_fp, 'w') as fw:
                    for line in fr:
                        line = os.path.expandvars(line)

                        m = self.SDKCONFIG_LINE_REGEX.match(line)
                        key = m.group(1) if m else None
                        if key == 'CONFIG_IDF_TARGET':
                            self._sdkconfig_files_defined_idf_target = m.group(2)

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
                        LOGGER.debug('=> Use sdkconfig file %s', f)
                        try:
                            os.unlink(expanded_fp)
                        except OSError:
                            LOGGER.debug('=> Failed to remove file %s', expanded_fp)
                        res.append(f)
                    else:
                        LOGGER.debug('=> Expand sdkconfig file %s to %s', f, expanded_fp)
                        res.append(expanded_fp)
                        # copy the related target-specific sdkconfig files
                        for target_specific_file in Path(f).parent.glob(os.path.basename(f) + f'.{self.target}'):
                            LOGGER.debug(
                                '=> Copy target-specific sdkconfig file %s to %s', target_specific_file, expanded_dir
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

        return [os.path.realpath(f) for f in res]

    @computed_field
    @property
    def build_status(self) -> BuildStatus:
        if self._build_status != BuildStatus.UNKNOWN:
            return self._build_status

        if not CONFIG.check_app_dependencies:
            self.build_status = BuildStatus.SHOULD_BE_BUILT
            return self._build_status

        if self.is_modified():
            self.build_status = BuildStatus.SHOULD_BE_BUILT
            return self._build_status

        # depends components?
        if CONFIG.check_app_dependencies and CONFIG.modified_components is not None:
            if self.depends_components:
                if set(self.depends_components).intersection(CONFIG.modified_components):
                    LOGGER.debug(
                        '=> Should be built. %s depends on components: %s, modified components %s',
                        self,
                        ', '.join(self.depends_components),
                        ', '.join(CONFIG.modified_components),
                    )
                    self.build_status = BuildStatus.SHOULD_BE_BUILT
                    return self._build_status

                # if current app defined depends_components, but no dependent components modified,
                # this app should not be built
                self.build_status = BuildStatus.SKIPPED
                self.skipped_reason = (
                    'No depends_components modified. {} depends on components: {}, modified components {}'.format(
                        self,
                        ', '.join(self.depends_components),
                        ', '.join(CONFIG.modified_components),
                    )
                )
                return self._build_status

        # or depends file patterns?
        if CONFIG.check_app_dependencies and CONFIG.modified_files is not None:
            if self.depends_filepatterns:
                if CONFIG.matches_modified_files(self.depends_filepatterns):
                    LOGGER.debug(
                        '=> Should be built. %s depends on file patterns: %s, modified files %s',
                        self,
                        ', '.join(self.depends_filepatterns),
                        ', '.join(CONFIG.modified_files),
                    )
                    self.build_status = BuildStatus.SHOULD_BE_BUILT
                    return self._build_status

                # if current app defined depends_filepatterns, but no dependent files modified,
                # this app should not be built
                self.build_status = BuildStatus.SKIPPED
                return self._build_status

        # not decided, leave it to the build stage `idf.py reconfigure`
        self.build_status = BuildStatus.NOT_DECIDED
        return self._build_status

    @build_status.setter
    def build_status(self, value: BuildStatus):
        self._build_status = value

    ############################
    # Un-serialized Properties #
    ############################
    @cached_property  # calculated once
    def name(self) -> str:
        return os.path.basename(self.app_dir)

    @property
    def build_path(self) -> str:
        if os.path.isabs(self.build_dir):
            return self.build_dir

        return str(to_absolute_path(os.path.join(self.work_dir, self.build_dir)))

    @property
    def depends_components(self) -> t.List[str]:
        if CONFIG.manifest:
            return CONFIG.manifest.depends_components(self.app_dir)

        return []

    @property
    def depends_filepatterns(self) -> t.List[str]:
        if CONFIG.manifest:
            return CONFIG.manifest.depends_filepatterns(self.app_dir)

        return []

    @property
    def supported_targets(self) -> t.List[str]:
        if CONFIG.manifest:
            return CONFIG.manifest.enable_build_targets(
                self.app_dir, self.sdkconfig_files_defined_idf_target, self.config_name
            )

        if self.sdkconfig_files_defined_idf_target:
            return [self.sdkconfig_files_defined_idf_target]

        return CONFIG.default_build_targets

    @property
    def verified_targets(self) -> t.List[str]:
        if CONFIG.manifest:
            return CONFIG.manifest.enable_test_targets(
                self.app_dir, self.sdkconfig_files_defined_idf_target, self.config_name
            )

        return []

    ###########
    # Methods #
    ###########
    @classmethod
    def set_ignore_warns_regexes(
        cls,
        *,
        ignore_warning_strs: t.Optional[t.List[str]] = None,
        ignore_warning_files: t.Optional[t.List[t.TextIO]] = None,
    ) -> None:
        ignore_warnings_regexes = []
        for s in ignore_warning_strs or []:
            ignore_warnings_regexes.append(re.compile(s))
        for f in ignore_warning_files or []:
            for s in f:
                ignore_warnings_regexes.append(re.compile(s.strip()))
        App.IGNORE_WARNS_REGEXES = ignore_warnings_regexes

    @abstractmethod
    def build(self) -> str:
        """
        Build the app.

        :return: True if build successfully, otherwise False
        """
        pass

    def write_size_json(self):
        map_file = find_first_match('*.map', self.build_path)
        if not map_file:
            LOGGER.warning(
                '.map file not found. Cannot write size json to file: %s',
                self.size_json_path,
            )
            return

        subprocess_run(
            (
                [
                    sys.executable,
                    str(IDF_SIZE_PY),
                ]
                + (['--json'] if IDF_VERSION < Version('5.1') else ['--format', 'json'])
                + [
                    '-o',
                    self.size_json_path,
                    map_file,
                ]
            ),
            check=True,
        )
        LOGGER.info('=> Generated size info to %s', self.size_json_path)

    def is_error_or_warning(self, line: str) -> t.Tuple[bool, bool]:
        """
        Check if the line is an error or warning, and if the warning is ignored or not.

        :param line: the line to check
        :return: a tuple of (is_error_or_warning, is_ignored)
        """
        if not self.LOG_ERROR_WARNING_REGEX.search(line):
            return False, False

        is_ignored = False
        for ignored in self.IGNORE_WARNS_REGEXES:
            if re.search(ignored, line):
                is_ignored = True
                break

        return True, is_ignored

    @classmethod
    @abstractmethod
    def is_app(cls, path: str) -> bool:
        """
        Check if the path is an app or not.

        :param path: the path to check
        :return: True if the path is an app, False otherwise
        """
        pass

    def is_modified(self) -> bool:
        """
        Check if the app is modified or not.

        .. note::

            .md files are ignored.

        :return: True if the app is modified, False otherwise
        """
        _app_dir_fullpath = to_absolute_path(self.app_dir)
        if CONFIG.modified_files:
            for f in CONFIG.modified_files:
                _f_fullpath = to_absolute_path(f)
                if _f_fullpath.parts[-1].endswith('.md'):
                    continue

                if _app_dir_fullpath in _f_fullpath.parents:
                    return True

        return False


class CMakeApp(App):
    BUILD_SYSTEM: ClassVar[str] = 'cmake'

    # If these keys are present in sdkconfig.defaults, they will be extracted and passed to CMake
    SDKCONFIG_TEST_OPTS: ClassVar[t.List[str]] = [
        'EXCLUDE_COMPONENTS',
        'TEST_EXCLUDE_COMPONENTS',
        'TEST_COMPONENTS',
    ]
    # These keys in sdkconfig.defaults are not propagated to the final sdkconfig file:
    SDKCONFIG_IGNORE_OPTS: ClassVar[t.List[str]] = ['TEST_GROUPS']
    # While ESP-IDF component CMakeLists files can be identified by the presence of 'idf_component_register' string,
    # there is no equivalent for the project CMakeLists files. This seems to be the best option...
    CMAKE_PROJECT_LINE: ClassVar[str] = r'include($ENV{IDF_PATH}/tools/cmake/project.cmake)'

    # ------------------
    # Instance variables
    # ------------------
    cmake_vars: t.Dict[str, str] = {}

    def build(self) -> bool:
        LOGGER.debug('=> Preparing...')
        if self.work_dir != self.app_dir:
            if os.path.exists(self.work_dir):
                LOGGER.debug('==> Work directory %s exists, removing', self.work_dir)
                if not self.dry_run:
                    shutil.rmtree(self.work_dir)
            LOGGER.debug('==> Copying app from %s to %s', self.app_dir, self.work_dir)
            if not self.dry_run:
                shutil.copytree(self.app_dir, self.work_dir)

        if os.path.exists(self.build_path):
            LOGGER.debug('==> Build directory %s exists, removing', self.build_path)
            if not self.dry_run:
                shutil.rmtree(self.build_path)

        if not self.dry_run:
            os.makedirs(self.build_path)

        sdkconfig_file = os.path.join(self.work_dir, 'sdkconfig')
        if os.path.exists(sdkconfig_file):
            LOGGER.debug('==> Removing sdkconfig file: %s', sdkconfig_file)
            if not self.dry_run:
                os.unlink(sdkconfig_file)

        if self.build_log_path:
            LOGGER.info('=> Writing build log to %s', self.build_log_path)

        if self.dry_run:
            self.build_status = BuildStatus.SKIPPED
            self.skipped_reason = 'dry run'

            LOGGER.debug('==> Skipping... (dry run)')
            return True

        if self.build_log_path:
            log_file = open(self.build_log_path, 'w')
        else:
            # delete manually later, used for tracking debugging info
            log_file = tempfile.NamedTemporaryFile('w', delete=False)

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

        if (
            CONFIG.check_app_dependencies
            and CONFIG.modified_components is not None
            and self.build_status == BuildStatus.NOT_DECIDED
        ):
            subprocess_run(
                common_args + ['reconfigure'],
                log_terminal=False if self.build_log_path else True,
                log_fs=log_file,
                check=True,
                additional_env_dict=additional_env_dict,
            )

            with open(os.path.join(self.build_path, PROJECT_DESCRIPTION_JSON)) as fr:
                build_components = {item for item in json.load(fr)['build_components'] if item}

            if not build_components.intersection(CONFIG.modified_components):
                self.build_status = BuildStatus.SKIPPED
                self.skipped_reason = (
                    f'No depends_components modified. '
                    f'{self} depends on components: {", ".join(self.depends_components)},'
                    f' modified components {", ".join(CONFIG.modified_components)}'
                )
                return False
            else:
                self.build_status = BuildStatus.SHOULD_BE_BUILT

        if self.build_status == BuildStatus.SKIPPED:
            LOGGER.info('=> Skip building...')
            return False

        # idf.py build
        build_args = deepcopy(common_args)
        if self.cmake_vars:
            for key, val in self.cmake_vars.items():
                build_args.append(f'-D{key}={val}')
            if 'TEST_EXCLUDE_COMPONENTS' in self.cmake_vars and 'TEST_COMPONENTS' not in self.cmake_vars:
                build_args.append('-DTESTS_ALL=1')
            if 'CONFIG_APP_BUILD_BOOTLOADER' in self.cmake_vars:
                # In case if secure_boot is enabled then for bootloader build need to add `bootloader` cmd
                build_args.append('bootloader')
        build_args.append('build')
        if self.verbose:
            build_args.append('-v')

        returncode = subprocess_run(
            build_args,
            log_terminal=False if self.build_log_path else True,
            log_fs=log_file,
            additional_env_dict=additional_env_dict,
        )

        log_file.close()

        # help debug
        unignored_warnings: t.List[str] = []
        with open(log_file.name) as f:
            lines = [line.rstrip() for line in f.readlines() if line.rstrip()]
            for line in lines:
                is_error_or_warning, ignored = self.is_error_or_warning(line)
                if is_error_or_warning:
                    if ignored:
                        LOGGER.info('[Ignored warning] %s', line)
                    else:
                        LOGGER.warning(line)
                        unignored_warnings.append(line)

            if returncode != 0:
                # print last few lines to help debug
                LOGGER.error(
                    'Last %s lines from the build log "%s":',
                    self.LOG_DEBUG_LINES,
                    self.build_log_path,
                )
                for line in lines[-self.LOG_DEBUG_LINES :]:
                    LOGGER.error('%s', line)

        if returncode != 0:
            debug_lines = lines[-self.LOG_DEBUG_LINES :]
            self.build_status = BuildStatus.FAILED
            self.failed_reason = '\n'.join(debug_lines)
        else:
            self.build_status = BuildStatus.SUCCESS
            if self.size_json_path:
                self.write_size_json()

        if not self.preserve:
            LOGGER.info('=> Removing build directory %s', self.build_path)
            exclude_list = []
            if self.size_json_path:
                exclude_list.append(os.path.basename(self.size_json_path))
            if self.build_log_path:
                exclude_list.append(os.path.basename(self.build_log_path))

            rmdir(
                self.build_path,
                exclude_file_patterns=exclude_list,
            )

        if returncode != 0:
            raise BuildError(f'Build failed with exit code {returncode}')

        if self.check_warnings and unignored_warnings:
            self.build_status = BuildStatus.FAILED
            self.failed_reason = 'Build succeeded with unignored warnings:\n' + '\n'.join(unignored_warnings)
            raise BuildError('Build succeeded with unignored warnings')

        if unignored_warnings:
            LOGGER.warning('=> Build succeeded with unignored warnings')
        else:
            LOGGER.info('=> Build succeeded')

        return True

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
