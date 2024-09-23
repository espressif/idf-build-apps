# SPDX-FileCopyrightText: 2024 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import argparse
import enum
import inspect
import logging
import os
import re
import sys
import typing as t
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import AliasChoices, Field, computed_field, field_validator
from pydantic.fields import FieldInfo
from pydantic_core.core_schema import ValidationInfo
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)
from typing_extensions import Concatenate, ParamSpec

from . import SESSION_ARGS, App, setup_logging
from .constants import ALL_TARGETS
from .manifest.manifest import FolderRule, Manifest
from .utils import InvalidCommand, files_matches_patterns, semicolon_separated_str_to_list, to_absolute_path, to_list
from .vendors.pydantic_sources import PyprojectTomlConfigSettingsSource, TomlConfigSettingsSource

LOGGER = logging.getLogger(__name__)


class ValidateMethod(str, enum.Enum):
    TO_LIST = 'to_list'


@dataclass
class FieldMetadata:
    """
    dataclass field metadata. All fields are optional.
    Some fields are used in argparse while running :func:`add_args_to_parser`.

    :param validate_method: validate method for the field
    :param deprecates: deprecates field names, used in argparse
    :param shorthand: shorthand for the argument, used in argparse
    :param action: action for the argument, used in argparse
    :param nargs: nargs for the argument, used in argparse
    :param choices: choices for the argument, used in argparse
    :param type: type for the argument, used in argparse
    :param required: whether the argument is required, used in argparse
    """

    # validate method
    validate_method: t.Optional[t.List[str]] = None
    # the field description will be copied from the deprecates field if not specified
    deprecates: t.Optional[t.Dict[str, t.Dict[str, t.Any]]] = None
    shorthand: t.Optional[str] = None
    # argparse_kwargs
    action: t.Optional[str] = None
    nargs: t.Optional[str] = None
    choices: t.Optional[t.List[str]] = None
    type: t.Optional[t.Callable] = None
    required: bool = False
    # usually default is not needed. only set it when different from the default value of the field
    default: t.Any = None


P = ParamSpec('P')
T = t.TypeVar('T')


def _wrap_with_metadata(
    _: t.Callable[P, t.Any],
) -> t.Callable[[t.Callable[..., T]], t.Callable[Concatenate[t.Optional[FieldMetadata], P], T]]:
    """Patch the function signature with metadata args"""

    def return_func(func: t.Callable[..., T]) -> t.Callable[Concatenate[t.Optional[FieldMetadata], P], T]:
        return t.cast(t.Callable[Concatenate[t.Optional[FieldMetadata], P], T], func)

    return return_func


@_wrap_with_metadata(Field)
def field(meta: t.Optional[FieldMetadata], *args, **kwargs):
    """field with metadata"""
    f = Field(*args, **kwargs)
    f.metadata.append(meta)
    return f


def get_meta(f: FieldInfo) -> t.Optional[FieldMetadata]:
    """
    Get the metadata of the field

    :param f: field
    :return: metadata of the field if exists, None otherwise
    """
    for m in f.metadata:
        if isinstance(m, FieldMetadata):
            return m

    return None


class BaseArguments(BaseSettings):
    """Base settings class for all settings classes"""

    model_config = SettingsConfigDict(
        toml_file='.idf_build_apps.toml',
        pyproject_toml_table_header=('tool', 'idf-build-apps'),
        pyproject_toml_depth=sys.maxsize,
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
        return (
            init_settings,
            TomlConfigSettingsSource(settings_cls),
            PyprojectTomlConfigSettingsSource(settings_cls),
        )

    @field_validator('*', mode='before')
    @classmethod
    def validate_by_validate_methods(cls, v: t.Any, info: ValidationInfo):
        if info.field_name and info.field_name in cls.model_fields:
            f = cls.model_fields[info.field_name]
            meta = get_meta(f)
            if meta and meta.validate_method and ValidateMethod.TO_LIST in meta.validate_method:
                return to_list(v)

        return v


class GlobalArguments(BaseArguments):
    verbose: int = field(
        FieldMetadata(
            shorthand='-v',
            action='count',
        ),
        description='Verbosity level. By default set to WARNING. Specify -v for INFO, -vv for DEBUG',
        default=0,
    )
    log_file: t.Optional[str] = field(
        None,
        description='Path to the log file, if not specified logs will be printed to stderr',
        default=None,
    )
    no_color: bool = field(
        FieldMetadata(
            action='store_true',
        ),
        description='Disable colored output',
        default=False,
    )

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)

        setup_logging(self.verbose, self.log_file, not self.no_color)


class DependencyDrivenBuildArguments(GlobalArguments):
    manifest_files: t.Optional[t.List[t.Union[Path, str]]] = field(
        FieldMetadata(
            validate_method=[ValidateMethod.TO_LIST],
            deprecates={
                'manifest_file': {
                    'nargs': '+',
                },
            },
            nargs='+',
        ),
        description='Path to the manifest files which contains the build test rules of the apps',
        validation_alias=AliasChoices('manifest_files', 'manifest_file'),
        default=None,
    )
    manifest_rootpath: str = field(
        None,
        description='Root path to resolve the relative paths defined in the manifest files. '
        'By default set to the current directory',
        default=os.curdir,
    )
    modified_components: t.Optional[t.List[str]] = field(
        FieldMetadata(
            validate_method=[ValidateMethod.TO_LIST],
            type=semicolon_separated_str_to_list,
        ),
        description='semicolon-separated list of modified components',
        default=None,
    )
    modified_files: t.Optional[t.List[str]] = field(
        FieldMetadata(
            validate_method=[ValidateMethod.TO_LIST],
            type=semicolon_separated_str_to_list,
        ),
        description='semicolon-separated list of modified files',
        default=None,
    )
    deactivate_dependency_driven_build_by_components: t.Optional[t.List[str]] = field(
        FieldMetadata(
            validate_method=[ValidateMethod.TO_LIST],
            deprecates={
                'ignore_app_dependencies_components': {
                    'type': semicolon_separated_str_to_list,
                    'shorthand': '-ic',
                }
            },
            type=semicolon_separated_str_to_list,
            shorthand='-dc',
        ),
        description='semicolon-separated list of components. '
        'dependency-driven build feature will be deactivated when any of these components are modified',
        validation_alias=AliasChoices(
            'deactivate_dependency_driven_build_by_components', 'ignore_app_dependencies_components'
        ),
        default=None,
    )
    deactivate_dependency_driven_build_by_filepatterns: t.Optional[t.List[str]] = field(
        FieldMetadata(
            validate_method=[ValidateMethod.TO_LIST],
            deprecates={
                'ignore_app_dependencies_filepatterns': {
                    'type': semicolon_separated_str_to_list,
                    'shorthand': '-if',
                }
            },
            type=semicolon_separated_str_to_list,
            shorthand='-df',
        ),
        description='semicolon-separated list of file patterns. '
        'dependency-driven build feature will be deactivated when any of matched files are modified',
        validation_alias=AliasChoices(
            'deactivate_dependency_driven_build_by_filepatterns', 'ignore_app_dependencies_filepatterns'
        ),
        default=None,
    )
    check_manifest_rules: bool = field(
        FieldMetadata(
            action='store_true',
        ),
        description='Check if all folders defined in the manifest files exist. Fail if not',
        default=False,
    )
    compare_manifest_sha_filepath: t.Optional[str] = field(
        None,
        description='Path to the file containing the sha256 hash of the manifest rules. '
        'Compare the hash with the current manifest rules. '
        'All matched apps will be built if the corresponding manifest rule is modified',
        default=None,
    )

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)

        Manifest.CHECK_MANIFEST_RULES = self.check_manifest_rules
        if self.manifest_files:
            App.MANIFEST = Manifest.from_files(
                self.manifest_files,
                root_path=to_absolute_path(self.manifest_rootpath),
            )

        if self.deactivate_dependency_driven_build_by_components is not None:
            if self.modified_components is None:
                raise InvalidCommand(
                    'Must specify --deactivate-dependency-driven-build-by-components '
                    'together with --modified-components'
                )

        if self.deactivate_dependency_driven_build_by_filepatterns is not None:
            if self.modified_files is None:
                raise InvalidCommand(
                    'Must specify --deactivate-dependency-driven-build-by-filepatterns together with --modified-files'
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
    paths: t.List[str] = field(
        FieldMetadata(
            validate_method=[ValidateMethod.TO_LIST],
            shorthand='-p',
            nargs='*',
        ),
        description='Paths to the directories containing the apps. By default set to the current directory',
        default=os.curdir,
    )
    target: str = field(
        FieldMetadata(
            shorthand='-t',
        ),
        description='Filter the apps by target. By default set to "all"',
        default='all',
    )
    build_system: t.Union[str, t.Type[App]] = field(
        FieldMetadata(
            choices=['cmake', 'make'],
        ),
        description='Filter the apps by build system. By default set to "cmake"',
        default='cmake',
    )
    recursive: bool = field(
        FieldMetadata(
            action='store_true',
        ),
        description='Search for apps recursively under the specified paths',
        default=False,
    )
    exclude: t.Optional[t.List[str]] = field(
        FieldMetadata(
            validate_method=[ValidateMethod.TO_LIST],
            nargs='+',
        ),
        description='Ignore the specified directories while searching recursively',
        validation_alias=AliasChoices('exclude', 'exclude_list'),
        default=None,
    )
    work_dir: t.Optional[str] = field(
        None,
        description='Copy the app to this directory before building. '
        'By default set to the app directory. Can expand placeholders',
        default=None,
    )
    build_dir: str = field(
        None,
        description='Build directory for the app. By default set to "build". '
        'When set to relative path, it will be treated as relative to the app directory. '
        'Can expand placeholders',
        default='build',
    )
    build_log_filename: t.Optional[str] = field(
        FieldMetadata(
            deprecates={'build_log': {}},
        ),
        description='Log filename under the build directory instead of stdout. Can expand placeholders',
        validation_alias=AliasChoices('build_log_filename', 'build_log'),
        default=None,
    )
    size_json_filename: t.Optional[str] = field(
        FieldMetadata(
            deprecates={'size_file': {}},
        ),
        description='`idf.py size` output file under the build directory when specified. ' 'Can expand placeholders',
        validation_alias=AliasChoices('size_json_filename', 'size_file'),
        default=None,
    )
    config_rules: t.Optional[t.List[str]] = field(
        FieldMetadata(
            validate_method=[ValidateMethod.TO_LIST],
            deprecates={
                'config': {'nargs': '+'},
            },
            nargs='+',
        ),
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
    override_sdkconfig_items: t.Optional[str] = field(
        None,
        description='A comma-separated list of key=value pairs to override the sdkconfig items',
        default=None,
    )
    override_sdkconfig_files: t.Optional[str] = field(
        None,
        description='A comma-separated list of sdkconfig files to override the sdkconfig items. '
        'When set to relative path, it will be treated as relative to the current directory',
        default=None,
    )
    sdkconfig_defaults: t.Optional[str] = field(
        None,
        description='A semicolon-separated list of sdkconfig files passed to `idf.py -DSDKCONFIG_DEFAULTS`. '
        'SDKCONFIG_DEFAULTS environment variable is used when not specified',
        default=os.getenv('SDKCONFIG_DEFAULTS', None),
    )
    check_warnings: bool = field(
        FieldMetadata(
            action='store_true',
        ),
        description='Check for warnings in the build output. Fail if any warnings are found',
        default=False,
    )
    default_build_targets: t.Optional[t.List[str]] = field(
        None,
        description='space-separated list of the default enabled build targets for the apps. '
        'When not specified, the default value is the targets listed by `idf.py --list-targets`',
        default=None,
    )
    enable_preview_targets: bool = field(
        FieldMetadata(
            action='store_true',
        ),
        description='When enabled, the default build targets will be set to all apps, '
        'including the preview targets. As the targets defined in `idf.py --list-targets --preview`',
        default=False,
    )
    include_skipped_apps: bool = field(
        FieldMetadata(
            action='store_true',
        ),
        description='Include the skipped apps in the output, together with the enabled ones',
        default=False,
    )
    include_disabled_apps: bool = field(
        FieldMetadata(
            action='store_true',
        ),
        description='Include the disabled apps in the output, together with the enabled ones',
        default=False,
    )
    include_all_apps: bool = field(
        FieldMetadata(
            action='store_true',
        ),
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

        if self.default_build_targets:
            default_build_targets = []
            for target in self.default_build_targets:
                if target not in ALL_TARGETS:
                    LOGGER.warning(
                        f'Ignoring... Unrecognizable target {target} specified with "--default-build-targets". '
                        f'Current ESP-IDF available targets: {ALL_TARGETS}'
                    )
                elif target not in default_build_targets:
                    default_build_targets.append(target)
            self.default_build_targets = default_build_targets
            LOGGER.info('Overriding default build targets to %s', self.default_build_targets)
            FolderRule.DEFAULT_BUILD_TARGETS = self.default_build_targets
        elif self.enable_preview_targets:
            self.default_build_targets = deepcopy(ALL_TARGETS)
            LOGGER.info('Overriding default build targets to %s', self.default_build_targets)
            FolderRule.DEFAULT_BUILD_TARGETS = self.default_build_targets

        if self.override_sdkconfig_items or self.override_sdkconfig_items:
            SESSION_ARGS.set(self)


class FindArguments(FindBuildArguments):
    output: t.Optional[str] = field(
        FieldMetadata(
            shorthand='-o',
        ),
        description='Record the found apps to the specified file instead of stdout',
        default=None,
    )
    output_format: str = field(
        FieldMetadata(
            choices=['raw', 'json'],
        ),
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
    build_verbose: bool = field(
        FieldMetadata(
            action='store_true',
        ),
        description='Enable verbose output of the build system',
        default=False,
    )
    parallel_count: int = field(
        FieldMetadata(
            type=int,
        ),
        description='Number of parallel build jobs in total. '
        'Specified together with --parallel-index. '
        'The given apps will be divided into parallel_count parts, '
        'and the current run will build the parallel_index-th part',
        default=1,
    )
    parallel_index: int = field(
        FieldMetadata(
            type=int,
        ),
        description='Index (1-based) of the parallel build job. '
        'Specified together with --parallel-count. '
        'The given apps will be divided into parallel_count parts, '
        'and the current run will build the parallel_index-th part',
        default=1,
    )
    dry_run: bool = field(
        FieldMetadata(
            action='store_true',
        ),
        description='Skip the actual build, only print the build process',
        default=False,
    )
    keep_going: bool = field(
        FieldMetadata(
            action='store_true',
        ),
        description='Continue building the next app when the current build fails',
        default=False,
    )
    no_preserve: bool = field(
        FieldMetadata(
            action='store_true',
        ),
        description='Do not preserve the build directory after a successful build',
        default=False,
    )
    ignore_warning_strs: t.Optional[t.List[str]] = field(
        FieldMetadata(
            validate_method=[ValidateMethod.TO_LIST],
            deprecates={
                'ignore_warning_str': {'nargs': '+'},
            },
            nargs='+',
        ),
        description='space-separated list of patterns. '
        'Ignore the warnings in the build output that match the patterns',
        validation_alias=AliasChoices('ignore_warning_strs', 'ignore_warning_str'),
        default=None,
    )
    ignore_warning_files: t.Optional[t.List[str]] = field(
        FieldMetadata(
            deprecates={'ignore_warning_file': {}},
            nargs='+',
        ),
        description='Path to the files containing the patterns to ignore the warnings in the build output',
        validation_alias=AliasChoices('ignore_warning_files', 'ignore_warning_file'),
        default=None,
    )
    copy_sdkconfig: bool = field(
        FieldMetadata(
            action='store_true',
        ),
        description='Copy the sdkconfig file to the build directory',
        default=False,
    )

    # Attrs that support placeholders
    collect_size_info_filename: t.Optional[str] = field(
        None,
        description='Record size json filepath of the built apps to the specified file. '
        'Each line is a json string. Can expand placeholders @p',
        validation_alias=AliasChoices('collect_size_info_filename', 'collect_size_info'),
        default=None,
        exclude=True,  # computed field is used
    )
    collect_app_info_filename: t.Optional[str] = field(
        None,
        description='Record serialized app model of the built apps to the specified file. '
        'Each line is a json string. Can expand placeholders @p',
        validation_alias=AliasChoices('collect_app_info_filename', 'collect_app_info'),
        default=None,
        exclude=True,  # computed field is used
    )
    junitxml_filename: t.Optional[str] = field(
        None,
        description='Path to the junitxml file to record the build results. Can expand placeholder @p',
        validation_alias=AliasChoices('junitxml_filename', 'junitxml'),
        default=None,
        exclude=True,  # computed field is used
    )
    # used for expanding placeholders
    PARALLEL_INDEX_PLACEHOLDER: t.ClassVar[str] = '@p'  # replace it with the parallel index

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)

        ignore_warnings_regexes = []
        if self.ignore_warning_strs:
            for s in self.ignore_warning_strs:
                ignore_warnings_regexes.append(re.compile(s))
        if self.ignore_warning_files:
            for s in self.ignore_warning_files:
                ignore_warnings_regexes.append(re.compile(s.strip()))
        App.IGNORE_WARNS_REGEXES = ignore_warnings_regexes

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
    manifest_files: t.Optional[t.List[str]] = field(
        FieldMetadata(
            validate_method=[ValidateMethod.TO_LIST],
            nargs='+',
            required=True,
        ),
        description='Path to the manifest files which contains the build test rules of the apps',
        default=None,
    )

    output: t.Optional[str] = field(
        FieldMetadata(
            shorthand='-o',
            required=True,
        ),
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

    FieldMetadata is used to set the argparse options.

    :param argument_cls: argument class
    :param parser: argparse parser
    """
    for f_name, f in argument_cls.model_fields.items():
        f_meta = get_meta(f)
        if f_meta and f_meta.deprecates:
            for dep_f_name, dep_f_kwargs in f_meta.deprecates.items():
                _names = [_snake_case_to_cli_arg_name(dep_f_name)]
                _shorthand = dep_f_kwargs.pop('shorthand', None)
                if _shorthand:
                    _names.append(_shorthand)

                parser.add_argument(
                    *_names,
                    **dep_f_kwargs,
                    help=f'[Deprecated] Use {_snake_case_to_cli_arg_name(f_name)} instead',
                )

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
            if f_meta.nargs:
                kwargs['nargs'] = f_meta.nargs
            if f_meta.choices:
                kwargs['choices'] = f_meta.choices
            if f_meta.default:
                kwargs['default'] = f_meta.default
        if 'default' not in kwargs:
            kwargs['default'] = f.default

        parser.add_argument(
            *names,
            **kwargs,
            help=f.description,
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


def apply_config_file(config_file: t.Optional[str]) -> None:
    def _subclasses(klass: t.Type[T]) -> t.Set[t.Type[T]]:
        return set(klass.__subclasses__()).union([s for c in klass.__subclasses__() for s in _subclasses(c)])

    if config_file:
        BaseArguments.model_config['toml_file'] = str(config_file)
        # modify all subclasses
        for cls in _subclasses(BaseArguments):
            cls.model_config['toml_file'] = str(config_file)
