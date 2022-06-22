# SPDX-FileCopyrightText: 2022 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import os
import re
import shutil
import subprocess
import sys
from abc import abstractmethod

from . import LOGGER
from .constants import IDF_PY, SUPPORTED_TARGETS
from .manifest.manifest import Manifest
from .utils import BuildError, rmdir


class App:
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
    LOG_ERROR_WARNING = re.compile(r'(error|warning):', re.IGNORECASE)

    # Log this many trailing lines from a failed build log, also
    LOG_DEBUG_LINES = 25

    def __init__(
        self,
        app_dir,
        target,
        sdkconfig_path=None,
        config_name=None,
        work_dir=None,
        build_dir='build',
        build_log_path=None,
        preserve=True,
    ):  # type: (str, str, str | None, str | None, str | None, str, str | None, bool) -> None
        # These internal variables store the paths with environment variables and placeholders;
        # Public properties with similar names use the _expand method to get the actual paths.
        self._app_dir = app_dir
        self._work_dir = work_dir or app_dir
        self._build_dir = build_dir or 'build'
        self._build_log_path = build_log_path

        self.name = os.path.basename(os.path.realpath(app_dir))
        self.sdkconfig_path = sdkconfig_path
        self.config_name = config_name
        self.target = target

        # Some miscellaneous build properties which are set later, at the build stage
        self.dry_run = False
        self.index = None
        self.preserve = preserve
        self.verbose = False

    def __repr__(self):
        return '({}) App {} for target {}, sdkconfig {} in {}'.format(
            self.BUILD_SYSTEM,
            self.app_dir,
            self.target,
            self.sdkconfig_path or '(default)',
            self.build_path,
        )

    def __lt__(self, other):
        return self.app_dir < other.app_dir

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
        """
        :return: path of the build log file
        """
        return self._expand(self._build_log_path)

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
    def enable_build_targets(cls, path):
        if cls.MANIFEST:
            return cls.MANIFEST.enable_build_targets(path)

        return SUPPORTED_TARGETS

    @abstractmethod
    def build(self):
        pass


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

        log_file = None
        build_stdout = sys.stdout
        build_stderr = sys.stderr
        if self.build_log_path:
            LOGGER.info('Writing build log to %s', self.build_log_path)
            log_file = open(self.build_log_path, 'w')
            build_stdout = log_file
            build_stderr = log_file

        try:
            subprocess.check_call(args, stdout=build_stdout, stderr=build_stderr)
        except subprocess.CalledProcessError as e:
            if log_file:
                log_file.close()
                log_file = None  # prevent log file from being deleted in finally block
                # help debug by printing the last few lines of the log
                with open(self.build_log_path) as f:
                    lines = [
                        line.rstrip() for line in f.readlines() if line.rstrip()
                    ]  # non-empty lines
                    LOGGER.debug(
                        'Error and warning lines from "%s"', self.build_log_path
                    )
                    for line in lines:
                        if self.LOG_ERROR_WARNING.search(line):
                            LOGGER.warning('>>> %s', line)
                    LOGGER.debug(
                        'Last %s lines of "%s":',
                        self.LOG_DEBUG_LINES,
                        self.build_log_path,
                    )
                    for line in lines[-self.LOG_DEBUG_LINES :]:
                        LOGGER.debug('>>> %s', line)

            raise BuildError('Build failed with exit code {}'.format(e.returncode))
        else:
            if not self.preserve:
                LOGGER.info('Removing build directory %s', self.build_path)
                rmdir(self.build_path)
        finally:
            if log_file:
                log_file.close()

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
