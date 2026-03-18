# SPDX-FileCopyrightText: 2024-2026 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import argparse
import glob
import importlib
import inspect
import logging
import os
import re
import sys
import typing as t
from copy import deepcopy
from dataclasses import dataclass
from io import TextIOWrapper
from pathlib import Path
from string import Template
from typing import Annotated
from typing import Any

from pydantic import AliasChoices
from pydantic import BeforeValidator
from pydantic import Field
from pydantic import computed_field
from pydantic import field_validator
from pydantic.fields import FieldInfo
from pydantic_core.core_schema import ValidationInfo
from pydantic_settings import BaseSettings
from pydantic_settings import PydanticBaseSettingsSource
from pydantic_settings import SettingsConfigDict

from . import SESSION_ARGS
from . import App
from . import CMakeApp
from . import MakeApp
from . import setup_logging
from .constants import ALL_TARGETS
from .constants import IDF_BUILD_APPS_TOML_FN
from .constants import PREVIEW_TARGETS
from .constants import SUPPORTED_TARGETS
from .manifest.manifest import DEFAULT_BUILD_TARGETS
from .manifest.manifest import Manifest
from .manifest.manifest import reset_default_build_targets
from .utils import InvalidCommand
from .utils import files_matches_patterns
from .utils import semicolon_separated_str_to_list
from .utils import to_absolute_path
from .utils import to_list
from .vendors.pydantic_sources import PyprojectTomlConfigSettingsSource
from .vendors.pydantic_sources import TomlConfigSettingsSource

LOGGER = logging.getLogger(__name__)
CLI_DEFAULT_UNSET = object()


@dataclass
class CliOption:
    """Argparse-only metadata attached via ``Annotated``."""

    deprecates: t.Optional[t.Dict[str, t.Dict[str, t.Any]]] = None
    shorthand: t.Optional[str] = None
    action: t.Optional[str] = None
    nargs: t.Optional[str] = None
    choices: t.Optional[t.List[str]] = None
    type: t.Optional[t.Callable] = None
    required: bool = False
    default: t.Any = CLI_DEFAULT_UNSET
    hidden: bool = False


T = t.TypeVar('T')
TO_LIST_VALIDATOR = BeforeValidator(to_list)


def get_cli_option(f: FieldInfo) -> t.Optional[CliOption]:
    """
    Get the Annotated argparse metadata of the field.

    :param f: field
    :return: metadata of the field if exists, None otherwise
    """
    for m in f.metadata:
        if isinstance(m, CliOption):
            return m

    return None


def expand_vars(v: t.Optional[str]) -> t.Optional[str]:
    """
    Expand environment variables in the string. If the variable is not found, use an empty string.

    :param v: string to expand
    :return: expanded string or None if the input is None
    """
    if v is None:
        return None

    unknown_vars: t.Dict[str, str] = dict()
    while True:
        try:
            v = Template(v).substitute(os.environ, **unknown_vars)
        except KeyError as e:
            LOGGER.debug('Environment variable %s not found. use empty string', e)
            unknown_vars[e.args[0]] = ''
        else:
            break

    return v


class BaseArguments(BaseSettings):
    """Base settings class for all settings classes"""

    CONFIG_FILE_PATH: t.ClassVar[t.Optional[Path]] = None
    PYPROJECT_TOML_TABLE_HEADER: t.ClassVar[t.Tuple[str, ...]] = ('tool', 'idf-build-apps')
    PYPROJECT_TOML_DEPTH: t.ClassVar[int] = sys.maxsize

    model_config = SettingsConfigDict(
        extra='ignore',  # we're supporting pydantic <2.6 as well, so we ignore extra fields
        validate_by_alias=True,
        validate_by_name=True,
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: t.Type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,  # noqa: ARG003
        dotenv_settings: PydanticBaseSettingsSource,  # noqa: ARG003
        file_secret_settings: PydanticBaseSettingsSource,  # noqa: ARG003
    ) -> t.Tuple[PydanticBaseSettingsSource, ...]:
        sources: t.Tuple[PydanticBaseSettingsSource, ...] = (init_settings,)
        if cls.CONFIG_FILE_PATH is None:
            sources += (
                TomlConfigSettingsSource(
                    settings_cls,
                    toml_file=Path(IDF_BUILD_APPS_TOML_FN),
                    search_depth=cls.PYPROJECT_TOML_DEPTH,
                ),
            )
            sources += (
                PyprojectTomlConfigSettingsSource(
                    settings_cls,
                    toml_file=Path('pyproject.toml'),
                    search_depth=cls.PYPROJECT_TOML_DEPTH,
                    table_header=cls.PYPROJECT_TOML_TABLE_HEADER,
                ),
            )
        else:
            sources += (
                TomlConfigSettingsSource(
                    settings_cls,
                    toml_file=Path(cls.CONFIG_FILE_PATH),
                    search_depth=cls.PYPROJECT_TOML_DEPTH,
                ),
            )
            sources += (
                PyprojectTomlConfigSettingsSource(
                    settings_cls,
                    toml_file=Path(cls.CONFIG_FILE_PATH),
                    search_depth=cls.PYPROJECT_TOML_DEPTH,
                    table_header=cls.PYPROJECT_TOML_TABLE_HEADER,
                ),
            )

        return sources

    @field_validator('*', mode='before')
    @classmethod
    def expand_field_vars(cls, v: t.Any, info: ValidationInfo):
        if not info.field_name or info.field_name not in cls.model_fields:
            return v

        if isinstance(v, str):
            return expand_vars(v)
        if isinstance(v, list):
            return [expand_vars(item) if isinstance(item, str) else item for item in v]

        return v


class GlobalArguments(BaseArguments):
    verbose: Annotated[
        int,
        CliOption(
            shorthand='-v',
            action='count',
        ),
    ] = Field(
        description='Verbosity level. By default set to WARNING. Specify -v for INFO, -vv for DEBUG',
        default=0,
    )
    log_file: t.Optional[str] = Field(
        description='Path to the log file, if not specified logs will be printed to stderr',
        default=None,
    )
    no_color: Annotated[
        bool,
        CliOption(
            action='store_true',
        ),
    ] = Field(
        description='Disable colored output',
        default=False,
    )

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)

        setup_logging(self.verbose, self.log_file, not self.no_color)


class DependencyDrivenBuildArguments(GlobalArguments):
    manifest_files: Annotated[
        t.Optional[t.List[t.Union[Path, str]]],
        TO_LIST_VALIDATOR,
        CliOption(
            deprecates={
                'manifest_file': {
                    'nargs': '+',
                },
            },
            nargs='+',
        ),
    ] = Field(
        description='Path to the manifest files which contains the build test rules of the apps',
        validation_alias=AliasChoices('manifest_files', 'manifest_file'),
        default=None,
    )
    manifest_filepatterns: Annotated[
        t.Optional[t.List[str]],
        TO_LIST_VALIDATOR,
        CliOption(
            nargs='+',
        ),
    ] = Field(
        description='space-separated list of file glob patterns to search for the manifest files. '
        'The matched files will be loaded as the manifest files.',
        default=None,
    )
    manifest_exclude_regexes: Annotated[
        t.Optional[t.List[str]],
        TO_LIST_VALIDATOR,
        CliOption(
            nargs='+',
        ),
    ] = Field(
        description='space-separated list of regex to exclude when searching for manifest files. '
        'Files matching these patterns will be ignored. '
        'By default excludes files under "managed_components" directories.',
        default=['/managed_components/'],
    )
    manifest_rootpath: str = Field(
        description='Root path to resolve the relative paths defined in the manifest files. '
        'By default set to the current directory.',
        default=os.curdir,
    )
    modified_components: Annotated[
        t.Optional[t.List[str]],
        TO_LIST_VALIDATOR,
        CliOption(
            type=semicolon_separated_str_to_list,
        ),
    ] = Field(
        description='semicolon-separated list of modified components. '
        'If set to "", the value would be considered as None. '
        'If set to ";", the value would be considered as an empty list.',
        default=None,
    )
    modified_files: Annotated[
        t.Optional[t.List[str]],
        TO_LIST_VALIDATOR,
        CliOption(
            type=semicolon_separated_str_to_list,
        ),
    ] = Field(
        description='semicolon-separated list of modified files. '
        'If set to "", the value would be considered as None. '
        'If set to ";", the value would be considered as an empty list.',
        default=None,
    )
    deactivate_dependency_driven_build_by_components: Annotated[
        t.Optional[t.List[str]],
        TO_LIST_VALIDATOR,
        CliOption(
            deprecates={
                'ignore_app_dependencies_components': {
                    'type': semicolon_separated_str_to_list,
                    'shorthand': '-ic',
                }
            },
            type=semicolon_separated_str_to_list,
            shorthand='-dc',
        ),
    ] = Field(
        description='semicolon-separated list of components. '
        'dependency-driven build feature will be deactivated when any of these components are modified. '
        'Must be specified together with --modified-components. '
        'If set to "", the value would be considered as None. '
        'If set to ";", the value would be considered as an empty list.',
        validation_alias=AliasChoices(
            'deactivate_dependency_driven_build_by_components', 'ignore_app_dependencies_components'
        ),
        default=None,
    )
    common_components: Annotated[
        t.Optional[t.List[str]],
        TO_LIST_VALIDATOR,
        CliOption(
            type=semicolon_separated_str_to_list,
            shorthand='-rc',
        ),
    ] = Field(
        description='semicolon-separated list of components. '
        'expand the `- *common_components` placeholder in manifests. '
        'Must be specified together with --modified-components. '
        'If set to "", the value would be considered as None. '
        'If set to ";", the value would be considered as an empty list.',
        default=None,
    )
    deactivate_dependency_driven_build_by_filepatterns: Annotated[
        t.Optional[t.List[str]],
        TO_LIST_VALIDATOR,
        CliOption(
            deprecates={
                'ignore_app_dependencies_filepatterns': {
                    'type': semicolon_separated_str_to_list,
                    'shorthand': '-if',
                }
            },
            type=semicolon_separated_str_to_list,
            shorthand='-df',
        ),
    ] = Field(
        description='semicolon-separated list of file patterns. '
        'dependency-driven build feature will be deactivated when any of matched files are modified. '
        'Must be specified together with --modified-files. '
        'If set to "", the value would be considered as None. '
        'If set to ";", the value would be considered as an empty list.',
        validation_alias=AliasChoices(
            'deactivate_dependency_driven_build_by_filepatterns', 'ignore_app_dependencies_filepatterns'
        ),
        default=None,
    )
    check_manifest_rules: Annotated[
        bool,
        CliOption(
            action='store_true',
        ),
    ] = Field(
        description='Check if all folders defined in the manifest files exist. Fail if not',
        default=False,
    )
    compare_manifest_sha_filepath: t.Optional[str] = Field(
        description='Path to the file containing the hash of the manifest rules. '
        'Compare the hash with the current manifest rules. '
        'All matched apps will be built if the corresponding manifest rule is modified',
        default=None,
    )

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)

        if self.manifest_filepatterns:
            matched_paths = set()
            for pat in [to_absolute_path(p, self.manifest_rootpath) for p in self.manifest_filepatterns]:
                matched_paths.update(glob.glob(str(pat), recursive=True))

            exclude_regexes = {re.compile(regex) for regex in self.manifest_exclude_regexes or []}

            # Filter out files matching excluded patterns
            if matched_paths:
                filtered_paths = set()
                for path in matched_paths:
                    posix_path = Path(path).as_posix()
                    for regex in exclude_regexes:
                        if regex.search(posix_path):
                            LOGGER.debug(f'Excluding manifest file {path} due to excluded regex match')
                            break
                    else:
                        filtered_paths.add(path)

                matched_paths = filtered_paths

            if matched_paths:
                if self.manifest_files:
                    self.manifest_files.extend(matched_paths)
                else:
                    self.manifest_files = list(matched_paths)

        Manifest.CHECK_MANIFEST_RULES = self.check_manifest_rules
        if self.manifest_files:
            App.MANIFEST = Manifest.from_files(
                self.manifest_files,
                root_path=to_absolute_path(self.manifest_rootpath),
                common_components=self.common_components,
            )

    @property
    def dependency_driven_build_enabled(self) -> bool:
        """
        Check if the dependency-driven build feature is enabled

        :return: True if enabled, False otherwise
        """
        # not check since modified_components and modified_files are not passed
        if self.modified_components is None and self.modified_files is None:
            return False

        # not check since deactivate_dependency_driven_build_by_components is passed and matched
        if (
            self.deactivate_dependency_driven_build_by_components
            and self.modified_components is not None
            and set(self.modified_components).intersection(self.deactivate_dependency_driven_build_by_components)
        ):
            LOGGER.info(
                'Build all apps since modified components %s matches ignored components %s',
                ', '.join(self.modified_components),
                ', '.join(self.deactivate_dependency_driven_build_by_components),
            )
            return False

        # not check since deactivate_dependency_driven_build_by_filepatterns is passed and matched
        if (
            self.deactivate_dependency_driven_build_by_filepatterns
            and self.modified_files is not None
            and files_matches_patterns(
                self.modified_files, self.deactivate_dependency_driven_build_by_filepatterns, self.manifest_rootpath
            )
        ):
            LOGGER.info(
                'Build all apps since modified files %s matches ignored file patterns %s',
                ', '.join(self.modified_files),
                ', '.join(self.deactivate_dependency_driven_build_by_filepatterns),
            )
            return False

        return True

    @property
    def modified_manifest_rules_folders(self) -> t.Optional[t.Set[str]]:
        if self.compare_manifest_sha_filepath and App.MANIFEST is not None:
            return App.MANIFEST.diff_sha_with_filepath(self.compare_manifest_sha_filepath, use_abspath=True)

        return None


class FindBuildArguments(DependencyDrivenBuildArguments):
    _KNOWN_APP_CLASSES: t.ClassVar[t.Dict[str, t.Type[App]]] = {
        'cmake': CMakeApp,
        'make': MakeApp,
    }
    _LOADED_MODULE_APPS: t.ClassVar[t.Dict[str, t.Type[App]]] = {}

    paths: Annotated[
        t.List[str],
        TO_LIST_VALIDATOR,
        CliOption(
            shorthand='-p',
            nargs='*',
        ),
    ] = Field(
        description='Paths to the directories containing the apps. By default set to the current directory',
        default=os.curdir,  # type: ignore
    )
    target: Annotated[
        str,
        CliOption(
            shorthand='-t',
        ),
    ] = Field(
        description='Filter the apps by target. By default set to "all"',
        default='all',
    )
    extra_pythonpaths: Annotated[
        t.Optional[t.List[str]],
        TO_LIST_VALIDATOR,
        CliOption(
            nargs='+',
        ),
    ] = Field(
        description='space-separated list of additional Python paths to search for the app classes. '
        'Will be injected into the head of sys.path.',
        default=None,
    )
    build_system: t.Union[str, t.Type[App]] = Field(
        description='Filter the apps by build system. By default set to "cmake". '
        'Can be either "cmake", "make" or a custom App class path in format "module:class"',
        default='cmake',
    )
    recursive: Annotated[
        bool,
        CliOption(
            action='store_true',
        ),
    ] = Field(
        description='Search for apps recursively under the specified paths',
        default=False,
    )
    exclude: Annotated[
        t.Optional[t.List[str]],
        TO_LIST_VALIDATOR,
        CliOption(
            nargs='+',
        ),
    ] = Field(
        description='Ignore the specified directories while searching recursively',
        validation_alias=AliasChoices('exclude', 'exclude_list'),
        default=None,
    )
    work_dir: t.Optional[str] = Field(
        description='Copy the app to this directory before building. '
        'By default set to the app directory. Can expand placeholders',
        default=None,
    )
    build_dir: str = Field(
        description='Build directory for the app. By default set to "build". '
        'When set to relative path, it will be treated as relative to the app directory. '
        'Can expand placeholders',
        default='build',
    )
    build_log_filename: Annotated[
        t.Optional[str],
        CliOption(
            deprecates={'build_log': {}},
        ),
    ] = Field(
        description='Log filename under the build directory instead of stdout. Can expand placeholders',
        validation_alias=AliasChoices('build_log_filename', 'build_log'),
        default=None,
    )
    size_json_filename: Annotated[
        t.Optional[str],
        CliOption(
            deprecates={'size_file': {}},
        ),
    ] = Field(
        description='`idf.py size` output file under the build directory when specified. Can expand placeholders',
        validation_alias=AliasChoices('size_json_filename', 'size_file'),
        default=None,
    )
    size_json_extra_args: Annotated[
        t.Optional[t.List[str]],
        TO_LIST_VALIDATOR,
        CliOption(),
    ] = Field(
        description='Additional arguments to pass to esp_idf_size tool',
        default=None,
    )
    config_rules: Annotated[
        t.Optional[t.List[str]],
        TO_LIST_VALIDATOR,
        CliOption(
            deprecates={
                'config': {'nargs': '+'},
            },
            nargs='+',
        ),
    ] = Field(
        description='Defines the rules of building the project with pre-set sdkconfig files. '
        'Supports FILENAME[=NAME] or FILEPATTERN format. '
        'FILENAME is the filename of the sdkconfig file, relative to the app directory. '
        'Optional NAME is the name of the configuration. '
        'if not specified, the filename is used as the name. '
        'FILEPATTERN is the filename of the sdkconfig file with a single wildcard character (*). '
        'The NAME is the value matched by the wildcard',
        validation_alias=AliasChoices('config_rules', 'config_rules_str', 'config'),
        default=None,
    )
    override_sdkconfig_items: t.Optional[str] = Field(
        description='A comma-separated list of key=value pairs to override the sdkconfig items',
        default=None,
    )
    override_sdkconfig_files: t.Optional[str] = Field(
        description='A comma-separated list of sdkconfig files to override the sdkconfig items. '
        'When set to relative path, it will be treated as relative to the current directory',
        default=None,
    )
    sdkconfig_defaults: t.Optional[str] = Field(
        description='A semicolon-separated list of sdkconfig files passed to `idf.py -DSDKCONFIG_DEFAULTS`. '
        'SDKCONFIG_DEFAULTS environment variable is used when not specified',
        default=os.getenv('SDKCONFIG_DEFAULTS', None),
    )
    check_warnings: Annotated[
        bool,
        CliOption(
            action='store_true',
        ),
    ] = Field(
        description='Check for warnings in the build output. Fail if any warnings are found',
        default=False,
    )
    default_build_targets: Annotated[
        t.Optional[t.List[str]],
        TO_LIST_VALIDATOR,
        CliOption(
            nargs='+',
        ),
    ] = Field(
        description='space-separated list of the default enabled build targets for the apps. '
        'When not specified, the default value is the targets listed by `idf.py --list-targets`.',
        default=None,
    )
    additional_build_targets: Annotated[
        t.Optional[t.List[str]],
        TO_LIST_VALIDATOR,
        CliOption(
            nargs='+',
        ),
    ] = Field(
        description='space-separated list of additional build targets to add to the default enabled build targets',
        default=None,
    )
    enable_preview_targets: Annotated[
        bool,
        CliOption(
            action='store_true',
        ),
    ] = Field(
        description='When enabled, PREVIEW_TARGETS will be added to the default enabled build targets',
        default=False,
    )
    disable_targets: Annotated[
        t.Optional[t.List[str]],
        TO_LIST_VALIDATOR,
        CliOption(
            nargs='+',
        ),
    ] = Field(
        description='space-separated list of targets that should be disabled to all apps.',
        default=None,
    )
    include_skipped_apps: Annotated[
        bool,
        CliOption(
            action='store_true',
        ),
    ] = Field(
        description='Include the skipped apps in the output, together with the enabled ones',
        default=False,
    )
    include_disabled_apps: Annotated[
        bool,
        CliOption(
            action='store_true',
        ),
    ] = Field(
        description='Include the disabled apps in the output, together with the enabled ones',
        default=False,
    )
    include_all_apps: Annotated[
        bool,
        CliOption(
            action='store_true',
        ),
    ] = Field(
        description='Include skipped, and disabled apps in the output, together with the enabled ones',
        default=False,
    )

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)

        if not self.paths:
            raise InvalidCommand('At least one path must be specified')

        if not self.target:
            LOGGER.debug('--target is missing. Set --target as "all".')
            self.target = 'all'

        reset_default_build_targets()  # reset first then judge again

        # Build the target set by combining the options
        default_build_targets: t.List[str] = []
        # Step 1: Determine base targets
        if self.default_build_targets:
            LOGGER.info('--default-build-targets is set, using `%s`', self.default_build_targets)
            default_build_targets = deepcopy(self.default_build_targets)
        elif SUPPORTED_TARGETS:
            LOGGER.info('Using default SUPPORTED_TARGETS: %s', SUPPORTED_TARGETS)
            default_build_targets = deepcopy(SUPPORTED_TARGETS)

        if self.enable_preview_targets:
            LOGGER.info('--enable-preview-targets is set, adding preview targets `%s`', PREVIEW_TARGETS)
            default_build_targets.extend(PREVIEW_TARGETS)

        if self.additional_build_targets:
            LOGGER.info('--additional-build-targets is set, adding `%s`', self.additional_build_targets)
            default_build_targets.extend(self.additional_build_targets)

        res = []
        for _t in set(default_build_targets):
            if _t not in ALL_TARGETS:
                LOGGER.warning(
                    f'Ignoring... Unrecognizable target {_t} specified. '
                    f'Current ESP-IDF available targets: {ALL_TARGETS}'
                )
                continue

            if self.disable_targets and _t in self.disable_targets:
                LOGGER.info(f'Ignoring... Target {_t} is in the disabled targets list.')
                continue

            res.append(_t)
        self.default_build_targets = sorted(res)
        DEFAULT_BUILD_TARGETS.set(self.default_build_targets)

        # Override sdkconfig files/items
        if self.override_sdkconfig_files or self.override_sdkconfig_items:
            SESSION_ARGS.set(self)

        # update PYTHONPATH
        if self.extra_pythonpaths:
            LOGGER.debug('Adding extra Python paths: %s', self.extra_pythonpaths)
            for path in self.extra_pythonpaths:
                abs_path = to_absolute_path(path)
                if abs_path not in sys.path:
                    sys.path.insert(0, abs_path)

        # load build system
        # here could be a string or a class of type App
        if not isinstance(self.build_system, str):
            # do nothing, only cache
            self._KNOWN_APP_CLASSES[self.build_system('', '').build_system] = self.build_system
            return

        # here could only be a string
        if self.build_system in self._KNOWN_APP_CLASSES:
            self.build_system = self._KNOWN_APP_CLASSES[self.build_system]
            return

        if ':' not in self.build_system:
            raise ValueError(
                f'Invalid build system: {self.build_system}. '
                f'Known build systems: {", ".join(self._KNOWN_APP_CLASSES.keys())}'
            )

        # here could only be a string in format "module:class"
        if self.build_system in self._LOADED_MODULE_APPS:
            self.build_system = self._LOADED_MODULE_APPS[self.build_system]
            return

        # here could only be a string in format "module:class", and not loaded yet
        module_path, class_name = self.build_system.split(':')
        try:
            module = importlib.import_module(module_path)
        except ImportError as e:
            raise ImportError(f'Failed to import module {module_path}. Error: {e!s}')

        try:
            app_cls = getattr(module, class_name)
            if not issubclass(app_cls, App):
                raise ValueError(f'Class {class_name} must be a subclass of App')
        except (ValueError, AttributeError):
            raise ValueError(f'Class {class_name} not found in module {module_path}')

        self._LOADED_MODULE_APPS[self.build_system] = app_cls
        self._KNOWN_APP_CLASSES[app_cls('', '').build_system] = app_cls

        self.build_system = app_cls


class FindArguments(FindBuildArguments):
    output: Annotated[
        t.Optional[str],
        CliOption(
            shorthand='-o',
        ),
    ] = Field(
        description='Record the found apps to the specified file instead of stdout',
        default=None,
    )
    output_format: Annotated[
        t.Literal['raw', 'json'],
        CliOption(choices=['raw', 'json']),
    ] = Field(
        description='Output format of the found apps. '
        'In "raw" format, each line is a json string serialized from the app model. '
        'In "json" format, the output is a json list of the serialized app models',
        default='raw',
    )

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)

        if self.include_all_apps:
            self.include_skipped_apps = True
            self.include_disabled_apps = True

        if self.output and self.output.endswith('.json') and self.output_format in ['raw', None]:
            LOGGER.debug('Detecting output file ends with ".json", writing as json file.')
            self.output_format = 'json'


class BuildArguments(FindBuildArguments):
    build_verbose: Annotated[
        bool,
        CliOption(
            action='store_true',
        ),
    ] = Field(
        description='Enable verbose output of the build system',
        default=False,
    )
    parallel_count: Annotated[
        int,
        CliOption(
            type=int,
        ),
    ] = Field(
        description='Number of parallel build jobs in total. '
        'Specified together with --parallel-index. '
        'The given apps will be divided into parallel_count parts, '
        'and the current run will build the parallel_index-th part',
        default=1,
    )
    parallel_index: Annotated[
        int,
        CliOption(
            type=int,
        ),
    ] = Field(
        description='Index (1-based) of the parallel build job. '
        'Specified together with --parallel-count. '
        'The given apps will be divided into parallel_count parts, '
        'and the current run will build the parallel_index-th part',
        default=1,
    )
    dry_run: Annotated[
        bool,
        CliOption(
            action='store_true',
        ),
    ] = Field(
        description='Skip the actual build, only print the build process',
        default=False,
    )
    keep_going: Annotated[
        bool,
        CliOption(
            action='store_true',
        ),
    ] = Field(
        description='Continue building the next app when the current build fails',
        default=False,
    )
    no_preserve: Annotated[
        bool,
        CliOption(
            action='store_true',
        ),
    ] = Field(
        description='Do not preserve the build directory after a successful build',
        default=False,
    )
    ignore_warning_strs: Annotated[
        t.Optional[t.List[str]],
        TO_LIST_VALIDATOR,
        CliOption(
            deprecates={
                'ignore_warning_str': {'nargs': '+'},
            },
            nargs='+',
        ),
    ] = Field(
        description='space-separated list of patterns. Ignore the warnings in the build output that match the patterns',
        validation_alias=AliasChoices('ignore_warning_strs', 'ignore_warning_str'),
        default=None,
    )
    ignore_warning_files: Annotated[
        t.Optional[t.List[t.Union[str, TextIOWrapper]]],
        TO_LIST_VALIDATOR,
        CliOption(
            deprecates={'ignore_warning_file': {}},
            nargs='+',
        ),
    ] = Field(
        description='Path to the files containing the patterns to ignore the warnings in the build output',
        validation_alias=AliasChoices('ignore_warning_files', 'ignore_warning_file'),
        default=None,
    )
    copy_sdkconfig: Annotated[
        bool,
        CliOption(
            action='store_true',
        ),
    ] = Field(
        description='Copy the sdkconfig file to the build directory',
        default=False,
    )

    # Attrs that support placeholders
    collect_size_info_filename: Annotated[
        t.Optional[str],
        CliOption(
            deprecates={'collect_size_info': {}},
            hidden=True,
        ),
    ] = Field(
        description='Record size json filepath of the built apps to the specified file. '
        'Each line is a json string. Can expand placeholders @p.',
        validation_alias=AliasChoices('collect_size_info_filename', 'collect_size_info'),
        default=None,
        exclude=True,  # computed field is used
    )
    collect_app_info_filename: Annotated[
        t.Optional[str],
        CliOption(
            deprecates={'collect_app_info': {}},
            hidden=True,
        ),
    ] = Field(
        description='Record serialized app model of the built apps to the specified file. '
        'Each line is a json string. Can expand placeholders @p.',
        validation_alias=AliasChoices('collect_app_info_filename', 'collect_app_info'),
        default=None,
        exclude=True,  # computed field is used
    )
    junitxml_filename: Annotated[
        t.Optional[str],
        CliOption(
            deprecates={'junitxml': {}},
            hidden=True,
        ),
    ] = Field(
        description='Path to the junitxml file to record the build results. Can expand placeholder @p.',
        validation_alias=AliasChoices('junitxml_filename', 'junitxml'),
        default=None,
        exclude=True,  # computed field is used
    )
    # used for expanding placeholders
    PARALLEL_INDEX_PLACEHOLDER: t.ClassVar[str] = '@p'  # replace it with the parallel index

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)

        patterns = []
        if self.ignore_warning_strs:
            patterns.extend(self.ignore_warning_strs)

        if self.ignore_warning_files:
            for f in self.ignore_warning_files:
                if isinstance(f, str):
                    with open(f) as fr:
                        patterns.extend(line.strip() for line in fr)
                else:
                    patterns.extend(f)

        App.IGNORE_WARNS_REGEXES = [re.compile(p.strip()) for p in patterns if p.strip()]

    @computed_field  # type: ignore
    @property
    def collect_size_info(self) -> t.Optional[str]:
        if self.collect_size_info_filename:
            return self.collect_size_info_filename.replace(self.PARALLEL_INDEX_PLACEHOLDER, str(self.parallel_index))

        return None

    @computed_field  # type: ignore
    @property
    def collect_app_info(self) -> t.Optional[str]:
        if self.collect_app_info_filename:
            return self.collect_app_info_filename.replace(self.PARALLEL_INDEX_PLACEHOLDER, str(self.parallel_index))

        return None

    @computed_field  # type: ignore
    @property
    def junitxml(self) -> t.Optional[str]:
        if self.junitxml_filename:
            return self.junitxml_filename.replace(self.PARALLEL_INDEX_PLACEHOLDER, str(self.parallel_index))

        return None


class DumpManifestShaArguments(GlobalArguments):
    manifest_files: Annotated[
        t.Optional[t.List[str]],
        TO_LIST_VALIDATOR,
        CliOption(
            nargs='+',
            required=True,
        ),
    ] = Field(
        description='Path to the manifest files which contains the build test rules of the apps',
        default=None,
    )
    common_components: Annotated[
        t.Optional[t.List[str]],
        TO_LIST_VALIDATOR,
        CliOption(
            type=semicolon_separated_str_to_list,
            shorthand='-rc',
        ),
    ] = Field(
        description='semicolon-separated list of components. '
        'expand the `- *common_components` placeholder in manifests. '
        'If set to "", the value would be considered as None. '
        'If set to ";", the value would be considered as an empty list.',
        default=None,
    )

    output: Annotated[
        t.Optional[str],
        CliOption(
            shorthand='-o',
            required=True,
        ),
    ] = Field(
        description='Path to the output file to record the sha256 hash of the manifest rules',
        default=None,
    )

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)

        if not self.manifest_files:
            raise InvalidCommand('Manifest files are required to dump the SHA values.')
        if not self.output:
            raise InvalidCommand('Output file is required to dump the SHA values.')


def _snake_case_to_cli_arg_name(s: str) -> str:
    return f'--{s.replace("_", "-")}'


def add_args_to_parser(argument_cls: t.Type[BaseArguments], parser: argparse.ArgumentParser) -> None:
    """
    Add arguments to the parser from the argument class.

    Annotated ``CliOption`` is used to set the argparse options.

    :param argument_cls: argument class
    :param parser: argparse parser
    """
    for f_name, f in argument_cls.model_fields.items():
        f_meta = get_cli_option(f)
        if f_meta and f_meta.deprecates:
            for dep_f_name, dep_f_kwargs in f_meta.deprecates.items():
                _names = [_snake_case_to_cli_arg_name(dep_f_name)]
                dep_kwargs = dict(dep_f_kwargs)
                _shorthand = dep_kwargs.pop('shorthand', None)
                if _shorthand:
                    _names.append(_shorthand)

                parser.add_argument(
                    *_names,
                    **dep_kwargs,
                    help=argparse.SUPPRESS,
                )

        if f_meta and f_meta.hidden:
            continue

        names = [_snake_case_to_cli_arg_name(f_name)]
        if f_meta and f_meta.shorthand:
            names.append(f_meta.shorthand)

        kwargs: t.Dict[str, t.Any] = {}
        if f_meta:
            if f_meta.type:
                kwargs['type'] = f_meta.type
            if f_meta.required:
                kwargs['required'] = True
            if f_meta.action:
                kwargs['action'] = f_meta.action
                # to make the CLI override config file work
                if f_meta.action == 'store_true':
                    kwargs['default'] = None

            if f_meta.nargs:
                kwargs['nargs'] = f_meta.nargs
            if f_meta.choices:
                kwargs['choices'] = f_meta.choices
            if f_meta.default is not CLI_DEFAULT_UNSET:
                kwargs['default'] = f_meta.default

        # here in CLI arguments, don't set the default to field.default
        # otherwise it will override the config file settings

        parser.add_argument(
            *names,
            **kwargs,
            help=f.description,
        )

        if f_meta and f_meta.action == 'store_true' and not f_name.startswith('no_'):
            no_name = f'--no-{f_name.replace("_", "-")}'
            parser.add_argument(
                no_name,
                dest=f_name,
                action='store_false',
                default=None,
                help=f'Disable {_snake_case_to_cli_arg_name(f_name)}',
            )


def add_args_to_obj_doc_as_params(argument_cls: t.Type[GlobalArguments], obj: t.Any = None) -> None:
    """
    Add arguments to the function as parameters.

    :param argument_cls: argument class
    :param obj: object to add the docstring to
    """
    _obj = obj or argument_cls
    _doc_str = _obj.__doc__ or ''
    _doc_str += '\n'

    for f_name, f in argument_cls.model_fields.items():
        # typing generic alias is not a class
        _annotation = f.annotation.__name__ if inspect.isclass(f.annotation) else f.annotation
        _doc_str += f'    :param {f_name}: {f.description}\n'
        _doc_str += f'    :type {f_name}: {_annotation}\n'

    _obj.__doc__ = _doc_str


def apply_config_file(config_file: t.Optional[str] = None, reset: bool = False) -> None:
    def _subclasses(klass: t.Type[T]) -> t.Set[t.Type[T]]:
        return set(klass.__subclasses__()).union([s for c in klass.__subclasses__() for s in _subclasses(c)])

    if reset:
        BaseArguments.CONFIG_FILE_PATH = None
        for cls in _subclasses(BaseArguments):
            cls.CONFIG_FILE_PATH = None

    if config_file:
        if os.path.isfile(config_file):
            p = Path(config_file)
            BaseArguments.CONFIG_FILE_PATH = p
            for cls in _subclasses(BaseArguments):
                cls.CONFIG_FILE_PATH = p
        else:
            LOGGER.warning(f'Config file {config_file} does not exist. Ignoring...')
