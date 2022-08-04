# SPDX-FileCopyrightText: 2022 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from abc import abstractmethod

from . import LOGGER
from .constants import IDF_PY, IDF_SIZE_PY
from .manifest.manifest import Manifest, FolderRule
from .utils import BuildError, rmdir, find_first_match, dict_from_sdkconfig

try:
    from typing import TextIO, Pattern
except ImportError:
    pass


class App:
    TARGET_PLACEHOLDER = '@t'  # replace it with self.target
    WILDCARD_PLACEHOLDER = '@w'  # replace it with the wildcard, usually the sdkconfig
    NAME_PLACEHOLDER = '@n'  # replace it with self.name
    FULL_NAME_PLACEHOLDER = '@f'  # replace it with escaped self.app_dir
    INDEX_PLACEHOLDER = '@i'  # replace it with the build index

    BUILD_SYSTEM = 'unknown'

    SDKCONFIG_LINE_REGEX = re.compile(r"^([^=]+)=\"?([^\"\n]*)\"?\n*$")

    SIZE_JSON = 'size.json'

    # could be assigned later, used for filtering out apps by supported_targets
    MANIFEST = None  # type: Manifest | None

    # This RE will match GCC errors and many other fatal build errors and warnings as well
    LOG_ERROR_WARNING_REGEX = re.compile(
        r'(?:error|warning):', re.MULTILINE | re.IGNORECASE
    )
    # Log this many trailing lines from a failed build log, also
    LOG_DEBUG_LINES = 25
    # IGNORE_WARNING_REGEX is a regex for warnings to be ignored. Could be assigned later
    IGNORE_WARNS_REGEXES = []  # type: list[Pattern]

    def __init__(
        self,
        app_dir,
        target,
        sdkconfig_path=None,
        config_name=None,
        work_dir=None,
        build_dir='build',
        build_log_path=None,
        size_json_path=None,
        check_warnings=False,
        preserve=True,
    ):  # type: (str, str, str | None, str | None, str | None, str, str | None, str | None, bool, bool) -> None
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
        if (
            self.FULL_NAME_PLACEHOLDER in path
        ):  # to avoid recursion to the call to app_dir in the next line:
            path = path.replace(
                self.FULL_NAME_PLACEHOLDER, self.app_dir.replace(os.path.sep, '_')
            )
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

    def build_prepare(self):  # type: () -> dict[str, str]
        if self.work_dir != self.app_dir:
            if os.path.exists(self.work_dir):
                LOGGER.debug('Work directory %s exists, removing', self.work_dir)
                if not self.dry_run:
                    shutil.rmtree(self.work_dir)
            LOGGER.debug('Copying app from %s to %s', self.app_dir, self.work_dir)
            if not self.dry_run:
                shutil.copytree(self.app_dir, self.work_dir)

        if os.path.exists(self.build_path):
            LOGGER.debug('Build directory %s exists, removing', self.build_path)
            if not self.dry_run:
                shutil.rmtree(self.build_path)

        if not self.dry_run:
            os.makedirs(self.build_path)

        # Prepare the sdkconfig file, from the contents of sdkconfig.defaults (if exists) and the contents of
        # build_info.sdkconfig_path, i.e. the config-specific sdkconfig file.
        #
        # Note: the build system supports taking multiple sdkconfig.defaults files via SDKCONFIG_DEFAULTS
        # CMake variable. However here we do this manually to perform environment variable expansion in the
        # sdkconfig files.
        sdkconfig_defaults_list = [
            'sdkconfig.defaults',
            'sdkconfig.defaults.' + self.target,
        ]
        if self.sdkconfig_path:
            sdkconfig_defaults_list.append(self.sdkconfig_path)

        sdkconfig_file = os.path.join(self.work_dir, 'sdkconfig')
        if os.path.exists(sdkconfig_file):
            LOGGER.debug('Removing sdkconfig file: %s', sdkconfig_file)
            if not self.dry_run:
                os.unlink(sdkconfig_file)

        LOGGER.debug('Creating sdkconfig file: %s', sdkconfig_file)
        cmake_vars = {}
        if not self.dry_run:
            with open(sdkconfig_file, 'w') as f_out:
                for sdkconfig_name in sdkconfig_defaults_list:
                    sdkconfig_path = os.path.join(self.work_dir, sdkconfig_name)
                    if not sdkconfig_path or not os.path.exists(sdkconfig_path):
                        continue
                    LOGGER.debug('Appending %s to sdkconfig', sdkconfig_name)
                    with open(sdkconfig_path, 'r') as f_in:
                        for line in f_in:
                            if not line.endswith('\n'):
                                line += '\n'
                            if isinstance(self, CMakeApp):
                                m = self.SDKCONFIG_LINE_REGEX.match(line)
                                key = m.group(1) if m else None
                                if key in self.SDKCONFIG_TEST_OPTS:
                                    cmake_vars[key] = m.group(2)
                                    continue
                                if key in self.SDKCONFIG_IGNORE_OPTS:
                                    continue
                            f_out.write(os.path.expandvars(line))
        else:
            for sdkconfig_name in sdkconfig_defaults_list:
                sdkconfig_path = os.path.join(self.work_dir, sdkconfig_name)
                if not sdkconfig_path:
                    continue
                LOGGER.debug('Considering sdkconfig %s', sdkconfig_path)
                if not os.path.exists(sdkconfig_path):
                    continue
                LOGGER.debug('Appending %s to sdkconfig', sdkconfig_name)

        return cmake_vars

    @classmethod
    def enable_build_targets(cls, path):  # type: (str) -> list[str]
        if cls.MANIFEST:
            res = cls.MANIFEST.enable_build_targets(path)
        else:
            res = FolderRule.DEFAULT_BUILD_TARGETS

        # check if there's CONFIG_IDF_TARGET in sdkconfig.defaults
        default_sdkconfig = os.path.join(path, 'sdkconfig.defaults')
        default_sdkconfig_target = None
        if os.path.isfile(default_sdkconfig):
            sdkconfig_dict = dict_from_sdkconfig(default_sdkconfig)
            if 'CONFIG_IDF_TARGET' in sdkconfig_dict:
                default_sdkconfig_target = sdkconfig_dict['CONFIG_IDF_TARGET']

        if default_sdkconfig_target:
            if len(res) > 1 or res != default_sdkconfig_target:
                LOGGER.warning(
                    'CONFIG_IDF_TARGET is set in %s. Set enable build targets to %s only.',
                    default_sdkconfig,
                    default_sdkconfig_target,
                )

            res = [default_sdkconfig_target]

        return res

    @classmethod
    def enable_test_targets(cls, path):  # type: (str) -> list[str]
        if cls.MANIFEST:
            return cls.MANIFEST.enable_test_targets(path)

        return []

    @property
    def supported_targets(self):
        return self.enable_build_targets(self.app_dir)

    @property
    def verified_targets(self):
        return self.enable_test_targets(self.app_dir)

    @abstractmethod
    def build(self):
        pass

    def write_size_json(self):
        map_file = find_first_match('*.map', self.build_path)
        if not map_file:
            LOGGER.warning(
                '.map file not found. Cannot write size json to file: %s',
                self.size_json_path,
            )
            return

        idf_size_args = [
            sys.executable,
            str(IDF_SIZE_PY),
            '--json',
            '-o',
            self.size_json_path,
            map_file,
        ]
        try:
            subprocess.check_call(idf_size_args)
        except subprocess.CalledProcessError as e:
            raise BuildError('Failed to run idf_size.py: {}'.format(e))

        LOGGER.debug('write size info to %s', self.size_json_path)

    def collect_size_info(self, output_fs):  # type: (TextIO) -> None
        if not os.path.isfile(self.size_json_path):
            self.write_size_json()

        size_info_dict = {
            'app_name': self.name,
            'config_name': self.config_name,
            'target': self.target,
            'path': self.size_json_path,
        }
        output_fs.write(json.dumps(size_info_dict) + '\n')

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

    def is_error_or_warning(
        self, line
    ):  # type: (str) -> tuple[bool, bool]  # is_error_or_warning, is_ignored
        if not self.LOG_ERROR_WARNING_REGEX.search(line):
            return False, False

        is_ignored = False
        for ignored in self.IGNORE_WARNS_REGEXES:
            if re.search(ignored, line):
                is_ignored = True
                break

        return True, is_ignored


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

    def build(self):
        cmake_vars = self.build_prepare()

        args = [
            sys.executable,
            str(IDF_PY),
            '-B',
            self.build_path,
            '-C',
            self.work_dir,
            '-DIDF_TARGET=' + self.target,
        ]
        if cmake_vars:
            for key, val in cmake_vars.items():
                args.append('-D{}={}'.format(key, val))
            if (
                'TEST_EXCLUDE_COMPONENTS' in cmake_vars
                and 'TEST_COMPONENTS' not in cmake_vars
            ):
                args.append('-DTESTS_ALL=1')
            if 'CONFIG_APP_BUILD_BOOTLOADER' in cmake_vars:
                # In case if secure_boot is enabled then for bootloader build need to add `bootloader` cmd
                args.append('bootloader')
        args.append('build')

        if self.verbose:
            args.append('-v')

        LOGGER.info('Running %s', ' '.join(args))

        if self.dry_run:
            return

        if self.build_log_path:
            LOGGER.info('Writing build log to %s', self.build_log_path)
            log_file = open(self.build_log_path, 'w')
        else:
            # delete manually later, used for tracking debugging info
            log_file = tempfile.NamedTemporaryFile('w', delete=False)

        old_idf_target_env = os.getenv('IDF_TARGET')
        os.environ['IDF_TARGET'] = self.target  # pass the cmake check
        p = subprocess.Popen(
            args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding='utf-8'
        )
        for line in p.stdout:
            if not self.build_log_path:
                sys.stdout.write(line)
            log_file.write(line)
        returncode = p.wait()
        if old_idf_target_env is not None:
            os.environ['IDF_TARGET'] = old_idf_target_env  # revert it back

        # help debug
        log_file.close()
        has_unignored_warning = False
        with open(log_file.name) as f:
            lines = [line.rstrip() for line in f.readlines() if line.rstrip()]
            for line in lines:
                is_error_or_warning, ignored = self.is_error_or_warning(line)
                if is_error_or_warning:
                    LOGGER.warning('>>> %s', line)
                    if not ignored:
                        has_unignored_warning = True

            if returncode != 0:
                # print last few lines to help debug
                LOGGER.debug(
                    'Last %s lines from the build log "%s":',
                    self.LOG_DEBUG_LINES,
                    self.build_log_path,
                )
                for line in lines[-self.LOG_DEBUG_LINES :]:
                    LOGGER.debug('>>> %s', line)

        if returncode == 0 and self.size_json_path:
            self.write_size_json()

        if not self.preserve:
            LOGGER.info('Removing build directory %s', self.build_path)
            rmdir(
                self.build_path,
                exclude_file_patterns=[
                    os.path.basename(self.size_json_path),
                    os.path.basename(self.build_log_path),
                ],
            )

        if returncode != 0:
            raise BuildError('Build failed with exit code {}'.format(returncode))

        if has_unignored_warning:
            raise BuildError('Build succeeded with warnings')

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
