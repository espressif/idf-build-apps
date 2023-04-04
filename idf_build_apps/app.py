# SPDX-FileCopyrightText: 2022-2023 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import json
import os
import re
import shutil
import sys
import tempfile
from abc import (
    abstractmethod,
)
from copy import (
    deepcopy,
)
from pathlib import (
    Path,
)

from packaging.version import (
    Version,
)

from . import (
    LOGGER,
)
from .constants import (
    DEFAULT_SDKCONFIG,
    IDF_PY,
    IDF_SIZE_PY,
    IDF_VERSION,
    PROJECT_DESCRIPTION_JSON,
)
from .manifest.manifest import (
    FolderRule,
    Manifest,
)
from .utils import (
    BuildError,
    find_first_match,
    rmdir,
    subprocess_run,
    to_list,
)

try:
    import typing as t
except ImportError:
    pass


class App(object):
    TARGET_PLACEHOLDER = '@t'  # replace it with self.target
    WILDCARD_PLACEHOLDER = '@w'  # replace it with the wildcard, usually the sdkconfig
    NAME_PLACEHOLDER = '@n'  # replace it with self.name
    FULL_NAME_PLACEHOLDER = '@f'  # replace it with escaped self.app_dir
    INDEX_PLACEHOLDER = '@i'  # replace it with the build index

    BUILD_SYSTEM = 'unknown'

    SDKCONFIG_LINE_REGEX = re.compile(r"^([^=]+)=\"?([^\"\n]*)\"?\n*$")

    # could be assigned later, used for filtering out apps by supported_targets
    MANIFEST = None  # type: Manifest | None

    # This RE will match GCC errors and many other fatal build errors and warnings as well
    LOG_ERROR_WARNING_REGEX = re.compile(r'(?:error|warning):', re.MULTILINE | re.IGNORECASE)
    # Log this many trailing lines from a failed build log, also
    LOG_DEBUG_LINES = 25
    # IGNORE_WARNING_REGEX is a regex for warnings to be ignored. Could be assigned later
    IGNORE_WARNS_REGEXES = []  # type: list[t.Pattern]

    def __init__(
        self,
        app_dir,  # type: str
        target,  # type: str
        sdkconfig_path=None,  # type: str | None
        config_name=None,  # type: str | None
        work_dir=None,  # type: str | None
        build_dir='build',  # type: str
        build_log_path=None,  # type: str | None
        size_json_path=None,  # type: str | None
        check_warnings=False,  # type: bool
        preserve=True,  # type: bool
        sdkconfig_defaults_str=None,  # type: str | None
    ):  # type: (...) -> None
        # These internal variables store the paths with environment variables and placeholders;
        # Public properties with similar names use the _expand method to get the actual paths.
        self._app_dir = app_dir
        self._work_dir = work_dir or app_dir
        self._build_dir = build_dir or 'build'
        self._build_log_path = build_log_path
        self._size_json_path = size_json_path

        self.name = os.path.basename(os.path.realpath(app_dir))
        self.sdkconfig_path = sdkconfig_path
        self.config_name = config_name
        self.target = target
        self.check_warnings = check_warnings
        self.preserve = preserve

        # Some miscellaneous build properties which are set later, at the build stage
        self.dry_run = False
        self.index = None
        self.verbose = False

        # sdkconfig attrs, use properties instead
        self._sdkconfig_defaults = self._get_sdkconfig_defaults(sdkconfig_defaults_str)
        self._sdkconfig_files = None
        self._sdkconfig_files_defined_target = None

        self._process_sdkconfig_files()

    def __repr__(self):
        return '({}) App {}, target {}, sdkconfig {}, build in {}'.format(
            self.BUILD_SYSTEM,
            self.app_dir,
            self.target,
            self.sdkconfig_path or '(default)',
            self.build_path,
        )

    def __lt__(self, other):
        if self.app_dir != other.app_dir:
            return self.app_dir < other.app_dir
        elif self.target != other.target:
            return self.target < other.target
        else:
            return self.config_name < other.config_name

    def __eq__(self, other):
        for props in [
            'app_dir',
            'work_dir',
            'build_dir',
            'size_json_path',
            'sdkconfig_files',
            'config_name',
            'target',
            'check_warnings',
            'preserve',
        ]:
            if getattr(self, props) != getattr(other, props):
                return False

        return True

    def __hash__(self):
        return hash(
            (
                self._app_dir,
                self._work_dir,
                self._build_dir,
                self._build_log_path,
                self._size_json_path,
                self.name,
                frozenset(self.sdkconfig_files),
                self.config_name,
                self.target,
                self.check_warnings,
                self.preserve,
            )
        )

    @staticmethod
    def _get_sdkconfig_defaults(sdkconfig_defaults_str=None):  # type: (str | None) -> list[str]
        if sdkconfig_defaults_str is not None:
            candidates = sdkconfig_defaults_str.split(';')
        elif os.getenv('SDKCONFIG_DEFAULTS', None) is not None:
            candidates = os.getenv('SDKCONFIG_DEFAULTS', None).split(';')
        else:
            candidates = [DEFAULT_SDKCONFIG]

        return candidates

    def _expand(self, path):  # type: (str) -> str
        """
        Internal method, expands any of the placeholders in {app,work,build} paths.
        """
        if not path:
            return path

        if self.index is not None:
            path = path.replace(self.INDEX_PLACEHOLDER, str(self.index))
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
    def app_dir(self):
        """
        :return: directory of the app
        """
        return self._expand(self._app_dir)

    @property
    def work_dir(self):
        """
        :return: directory where the app should be copied to, prior to the build.
        """
        return self._expand(self._work_dir)

    @property
    def build_dir(self):
        """
        :return: build directory, either relative to the work directory (if relative path is used) or absolute path.
        """
        return self._expand(self._build_dir)

    @property
    def build_path(self):
        if os.path.isabs(self.build_dir):
            return self.build_dir

        return os.path.realpath(os.path.join(self.work_dir, self.build_dir))

    @property
    def build_log_path(self):
        if self._build_log_path:
            return os.path.join(self.build_path, self._expand(self._build_log_path))

        return None

    @property
    def size_json_path(self):
        if self._size_json_path:
            return os.path.join(self.build_path, self._expand(self._size_json_path))

        return None

    def _process_sdkconfig_files(self):
        """
        Expand environment variables in default sdkconfig files and remove some CI
        related settings.
        """
        res = []

        for f in self._sdkconfig_defaults + ([self.sdkconfig_path] if self.sdkconfig_path else []):
            if not os.path.isabs(f):
                f = os.path.join(self.work_dir, f)

            if not os.path.isfile(f):
                LOGGER.debug('=> sdkconfig file %s not exists, skipping...', f)
                continue

            expanded_dir = os.path.join(self.work_dir, 'expanded_sdkconfig_files')
            expanded_fp = os.path.join(expanded_dir, os.path.basename(f))
            if not os.path.isdir(expanded_dir):
                os.makedirs(expanded_dir)

            with open(f) as fr:
                with open(expanded_fp, 'w') as fw:
                    for line in fr:
                        line = os.path.expandvars(line)

                        m = self.SDKCONFIG_LINE_REGEX.match(line)
                        key = m.group(1) if m else None
                        if key == 'CONFIG_IDF_TARGET':
                            self._sdkconfig_files_defined_target = m.group(2)

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
                        for target_specific_file in Path(f).parent.glob(
                            os.path.basename(f) + '.{}'.format(self.target)
                        ):
                            LOGGER.debug(
                                '=> Copy target-specific sdkconfig file %s to %s', target_specific_file, expanded_dir
                            )
                            shutil.copy(target_specific_file, expanded_dir)

        self._sdkconfig_files = res

    @property
    def sdkconfig_files_defined_idf_target(self):  # type: () -> str | None
        return self._sdkconfig_files_defined_target

    @property
    def sdkconfig_files(self):  # type: () -> list[str]
        return [os.path.realpath(file) for file in self._sdkconfig_files]

    @property
    def requires_components(self):  # type: () -> list[str]
        if self.MANIFEST:
            return self.MANIFEST.requires_components(self.app_dir)

        return []

    @property
    def supported_targets(self):
        if self.MANIFEST:
            return self.MANIFEST.enable_build_targets(self.app_dir, self.sdkconfig_files_defined_idf_target)

        if self.sdkconfig_files_defined_idf_target:
            return [self.sdkconfig_files_defined_idf_target]

        return FolderRule.DEFAULT_BUILD_TARGETS

    @property
    def verified_targets(self):
        if self.MANIFEST:
            return self.MANIFEST.enable_test_targets(self.app_dir, self.sdkconfig_files_defined_idf_target)

        return []

    @abstractmethod
    def build(
        self,
        depends_on_components=None,  # type: list[str] | str | None
        check_component_dependencies=False,  # type: bool
    ):  # type: (...) -> bool
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

    def collect_size_info(self, output_fs):  # type: (t.TextIO) -> None
        if not os.path.isfile(self.size_json_path):
            self.write_size_json()

        size_info_dict = {
            'app_name': self.name,
            'config_name': self.config_name,
            'target': self.target,
            'path': self.size_json_path,
        }
        output_fs.write(json.dumps(size_info_dict) + '\n')
        LOGGER.info('=> Recorded size info file path in %s', output_fs.name)

    def to_json(self):
        # keeping backward compatibility, only provide these stuffs
        return json.dumps(
            {
                'build_system': self.BUILD_SYSTEM,
                'app_dir': self.app_dir,
                'work_dir': self.work_dir,
                'build_dir': self.build_dir,
                'build_log_path': self.build_log_path,
                'sdkconfig': self.sdkconfig_path,
                'config': self.config_name,
                'target': self.target,
                'verbose': self.verbose,
                'preserve': self.preserve,
            }
        )

    def is_error_or_warning(self, line):  # type: (str) -> tuple[bool, bool]  # is_error_or_warning, is_ignored
        if not self.LOG_ERROR_WARNING_REGEX.search(line):
            return False, False

        is_ignored = False
        for ignored in self.IGNORE_WARNS_REGEXES:
            if re.search(ignored, line):
                is_ignored = True
                break

        return True, is_ignored

    @classmethod
    def is_app(cls, path):  # type: (str) -> bool
        raise NotImplementedError('Please implement this function in sub classes')


class CMakeApp(App):
    BUILD_SYSTEM = 'cmake'

    # If these keys are present in sdkconfig.defaults, they will be extracted and passed to CMake
    SDKCONFIG_TEST_OPTS = [
        'EXCLUDE_COMPONENTS',
        'TEST_EXCLUDE_COMPONENTS',
        'TEST_COMPONENTS',
    ]

    # These keys in sdkconfig.defaults are not propagated to the final sdkconfig file:
    SDKCONFIG_IGNORE_OPTS = ['TEST_GROUPS']

    # While ESP-IDF component CMakeLists files can be identified by the presence of 'idf_component_register' string,
    # there is no equivalent for the project CMakeLists files. This seems to be the best option...
    CMAKE_PROJECT_LINE = r'include($ENV{IDF_PATH}/tools/cmake/project.cmake)'

    def __init__(self, *args, **kwargs):
        self.cmake_vars = {}
        super(CMakeApp, self).__init__(*args, **kwargs)

    def build(
        self,
        depends_on_components=None,  # type: list[str] | str | None
        check_component_dependencies=False,  # type: bool
    ):  # type: (...) -> bool
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
            '-DIDF_TARGET={}'.format(self.target),
            # set to ";" to disable `default` when no such variable
            '-DSDKCONFIG_DEFAULTS={}'.format(';'.join(self.sdkconfig_files) if self.sdkconfig_files else ';'),
        ]

        depends_on_components = to_list(depends_on_components)
        if depends_on_components is not None and check_component_dependencies:
            subprocess_run(
                common_args + ['reconfigure'],
                log_terminal=False if self.build_log_path else True,
                log_fs=log_file,
                check=True,
                additional_env_dict=additional_env_dict,
            )

            with open(os.path.join(self.build_path, PROJECT_DESCRIPTION_JSON)) as fr:
                build_components = set(item for item in json.load(fr)['build_components'] if item)

            if not set(depends_on_components).intersection(set(build_components)):
                LOGGER.info(
                    '=> Skip building... app %s depends on components: %s, while current build based on component dependencies: %s',
                    self.app_dir,
                    build_components,
                    depends_on_components,
                )
                return False

        # idf.py build
        build_args = deepcopy(common_args)
        if self.cmake_vars:
            for key, val in self.cmake_vars.items():
                build_args.append('-D{}={}'.format(key, val))
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
        has_unignored_warning = False
        with open(log_file.name) as f:
            lines = [line.rstrip() for line in f.readlines() if line.rstrip()]
            for line in lines:
                is_error_or_warning, ignored = self.is_error_or_warning(line)
                if is_error_or_warning:
                    if ignored:
                        LOGGER.info('[Ignored warning] %s', line)
                    else:
                        LOGGER.warning('%s', line)
                        has_unignored_warning = True

            if returncode != 0:
                # print last few lines to help debug
                LOGGER.error(
                    'Last %s lines from the build log "%s":',
                    self.LOG_DEBUG_LINES,
                    self.build_log_path,
                )
                for line in lines[-self.LOG_DEBUG_LINES :]:
                    LOGGER.error('%s', line)

        if returncode == 0 and self.size_json_path:
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
            raise BuildError('Build failed with exit code {}'.format(returncode))

        if has_unignored_warning:
            raise BuildError('Build succeeded with warnings')

        LOGGER.info('=> Build succeeded')
        return True

    @classmethod
    def is_app(cls, path):  # type: (str) -> bool
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
