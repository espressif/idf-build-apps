# SPDX-FileCopyrightText: 2024 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0
"""
Arguments used in the CLI, and functions.

The reason that does not use pydantic models, but dataclasses

- poor autocomplete in IDE when using pydantic custom Fields with extra metadata
- pydantic Field alias is nice, but hard to customize, when
    - the deprecated field has a different nargs
"""

import argparse
import inspect
import logging
import os
import re
import typing as t
import warnings
from copy import deepcopy
from dataclasses import InitVar, asdict, dataclass, field, fields

from . import SESSION_ARGS, setup_logging
from .app import App
from .config import get_valid_config
from .constants import ALL_TARGETS
from .manifest.manifest import FolderRule, Manifest
from .utils import (
    InvalidCommand,
    Self,
    files_matches_patterns,
    semicolon_separated_str_to_list,
    to_absolute_path,
    to_list,
)

LOGGER = logging.getLogger(__name__)


@dataclass
class FieldMetadata:
    """
    dataclass field metadata. All fields are optional.
    Some fields are used in argparse while running :func:`add_args_to_parser`.

    :param description: description of the field
    :param deprecated_by: name of the field that deprecates this field
    :param shorthand: shorthand for the argument, used in argparse
    :param action: action for the argument, used in argparse
    :param nargs: nargs for the argument, used in argparse
    :param choices: choices for the argument, used in argparse
    :param type: type for the argument, used in argparse
    :param required: whether the argument is required, used in argparse
    :param default: default value, used in argparse
    """

    description: t.Optional[str] = None
    # when deprecated, the field description will be copied from the deprecated_by field if not specified
    deprecated_by: t.Optional[str] = None
    shorthand: t.Optional[str] = None
    # argparse_kwargs
    action: t.Optional[str] = None
    nargs: t.Optional[str] = None
    choices: t.Optional[t.List[str]] = None
    type: t.Optional[t.Callable] = None
    required: bool = False
    # usually default is not needed. only set it when different from the default value of the field
    default: t.Any = None


@dataclass
class GlobalArguments:
    """
    Global arguments used in all commands
    """

    config_file: t.Optional[str] = field(
        default=None,
        metadata=asdict(
            FieldMetadata(
                description='Path to the configuration file',
                shorthand='-c',
            )
        ),
    )
    verbose: int = field(
        default=0,
        metadata=asdict(
            FieldMetadata(
                description='Verbosity level. By default set to WARNING. Specify -v for INFO, -vv for DEBUG',
                shorthand='-v',
                action='count',
            )
        ),
    )
    log_file: t.Optional[str] = field(
        default=None,
        metadata=asdict(
            FieldMetadata(
                description='Path to the log file, if not specified logs will be printed to stderr',
            )
        ),
    )
    no_color: bool = field(
        default=False,
        metadata=asdict(
            FieldMetadata(
                description='Disable colored output',
                action='store_true',
            )
        ),
    )

    @classmethod
    def from_dict(cls, d: t.Dict[str, t.Any]) -> Self:
        """
        Create an instance from a dictionary. Ignore unknown keys.

        :param d: dictionary
        :return: instance
        """
        return cls(**{k: v for k, v in d.items() if k in {f.name for f in fields(cls)}})

    def __post_init__(self):
        self.apply_config()

    def __setattr__(self, key, value):
        if value == getattr(self, key, None):
            return

        _new_name_deprecated_name_dict = {}
        _deprecated_name_new_name_dict = {}
        for _n, _f in {f.name: f for f in fields(self)}.items():
            _meta = FieldMetadata(**_f.metadata)
            if _meta.deprecated_by:
                _new_name_deprecated_name_dict[_meta.deprecated_by] = _n
                _deprecated_name_new_name_dict[_n] = _meta.deprecated_by

        if key in _new_name_deprecated_name_dict:
            super().__setattr__(key, value)
            # set together with the deprecated field
            super().__setattr__(_new_name_deprecated_name_dict[key], value)
        elif key in _deprecated_name_new_name_dict:
            warnings.warn(
                f'Field {key} is deprecated by {_deprecated_name_new_name_dict[key]}. Will be removed in the future.'
            )
            super().__setattr__(key, value)
            # set together with the new field
            super().__setattr__(_deprecated_name_new_name_dict[key], value)
        else:
            super().__setattr__(key, value)

    def apply_config(self) -> None:
        """
        Apply the configuration file to the arguments
        """
        config_dict = get_valid_config(custom_path=self.config_file)
        if config_dict:
            for name, value in config_dict.items():
                if hasattr(self, name):
                    setattr(self, name, value)

        setup_logging(self.verbose, self.log_file, not self.no_color)


@dataclass
class DependencyDrivenBuildArguments(GlobalArguments):
    """
    Arguments used in the dependency-driven build feature.
    """

    manifest_file: t.Optional[t.List[str]] = field(
        default=None,
        metadata=asdict(
            FieldMetadata(
                deprecated_by='manifest_files',
                nargs='+',
            )
        ),
    )
    manifest_files: t.Optional[t.List[str]] = field(
        default=None,
        metadata=asdict(
            FieldMetadata(
                description='Path to the manifest files which contains the build test rules of the apps',
                nargs='+',
            )
        ),
    )
    manifest_rootpath: str = field(
        default=os.curdir,
        metadata=asdict(
            FieldMetadata(
                description='Root path to resolve the relative paths defined in the manifest files. '
                'By default set to the current directory',
            )
        ),
    )
    modified_components: t.Optional[t.List[str]] = field(
        default=None,
        metadata=asdict(
            FieldMetadata(
                description='semicolon-separated list of modified components',
                type=semicolon_separated_str_to_list,
            )
        ),
    )
    modified_files: t.Optional[t.List[str]] = field(
        default=None,
        metadata=asdict(
            FieldMetadata(
                description='semicolon-separated list of modified files',
                type=semicolon_separated_str_to_list,
            )
        ),
    )
    ignore_app_dependencies_components: t.Optional[t.List[str]] = field(
        default=None,
        metadata=asdict(
            FieldMetadata(
                deprecated_by='deactivate_dependency_driven_build_by_components',
                type=semicolon_separated_str_to_list,
                shorthand='-ic',
            )
        ),
    )
    deactivate_dependency_driven_build_by_components: t.Optional[t.List[str]] = field(
        default=None,
        metadata=asdict(
            FieldMetadata(
                description='semicolon-separated list of components. '
                'dependency-driven build feature will be deactivated when any of these components are modified',
                type=semicolon_separated_str_to_list,
                shorthand='-dc',
            )
        ),
    )
    ignore_app_dependencies_filepatterns: t.Optional[t.List[str]] = field(
        default=None,
        metadata=asdict(
            FieldMetadata(
                deprecated_by='deactivate_dependency_driven_build_by_filepatterns',
                type=semicolon_separated_str_to_list,
                shorthand='-if',
            )
        ),
    )
    deactivate_dependency_driven_build_by_filepatterns: t.Optional[t.List[str]] = field(
        default=None,
        metadata=asdict(
            FieldMetadata(
                description='semicolon-separated list of file patterns. '
                'dependency-driven build feature will be deactivated when any of matched files are modified',
                type=semicolon_separated_str_to_list,
                shorthand='-df',
            )
        ),
    )
    check_manifest_rules: bool = field(
        default=False,
        metadata=asdict(
            FieldMetadata(
                description='Check if all folders defined in the manifest files exist. Fail if not',
                action='store_true',
            )
        ),
    )
    compare_manifest_sha_filepath: t.Optional[str] = field(
        default=None,
        metadata=asdict(
            FieldMetadata(
                description='Path to the file containing the sha256 hash of the manifest rules. '
                'Compare the hash with the current manifest rules. '
                'All matched apps will be built if the cooresponding manifest rule is modified',
            )
        ),
    )

    def __post_init__(self):
        super().__post_init__()

        self.manifest_files = to_list(self.manifest_files)
        self.modified_components = to_list(self.modified_components)
        self.modified_files = to_list(self.modified_files)
        self.deactivate_dependency_driven_build_by_components = to_list(
            self.deactivate_dependency_driven_build_by_components
        )
        self.deactivate_dependency_driven_build_by_filepatterns = to_list(
            self.deactivate_dependency_driven_build_by_filepatterns
        )

        # Validation
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


def _os_curdir_as_list() -> t.List[str]:
    return [os.curdir]


@dataclass
class FindBuildArguments(DependencyDrivenBuildArguments):
    """
    Arguments used in both find and build commands
    """

    paths: t.List[str] = field(
        default_factory=_os_curdir_as_list,
        metadata=asdict(
            FieldMetadata(
                default=os.curdir,
                description='Paths to the directories containing the apps. By default set to the current directory',
                shorthand='-p',
                nargs='*',
            )
        ),
    )
    target: str = field(
        default='all',
        metadata=asdict(
            FieldMetadata(
                description='Filter the apps by target. By default set to "all"',
                shorthand='-t',
            )
        ),
    )
    build_system: t.Union[str, t.Type[App]] = field(
        default='cmake',
        metadata=asdict(
            FieldMetadata(
                description='Filter the apps by build system. By default set to "cmake"',
                choices=['cmake', 'make'],
            )
        ),
    )
    recursive: bool = field(
        default=False,
        metadata=asdict(
            FieldMetadata(
                description='Search for apps recursively under the specified paths',
                action='store_true',
            )
        ),
    )
    exclude_list: InitVar[t.Optional[t.List[str]]] = None
    exclude: t.Optional[t.List[str]] = field(
        default=None,
        metadata=asdict(
            FieldMetadata(
                description='Ignore the specified directories while searching recursively',
                nargs='+',
            )
        ),
    )
    work_dir: t.Optional[str] = field(
        default=None,
        metadata=asdict(
            FieldMetadata(
                description='Copy the app to this directory before building. '
                'By default set to the app directory. Can expand placeholders',
            )
        ),
    )
    build_dir: str = field(
        default='build',
        metadata=asdict(
            FieldMetadata(
                description='Build directory for the app. By default set to "build". '
                'When set to relative path, it will be treated as relative to the app directory. '
                'Can expand placeholders',
            )
        ),
    )
    build_log: t.Optional[str] = field(
        default=None,
        metadata=asdict(
            FieldMetadata(
                deprecated_by='build_log_filename',
            )
        ),
    )
    build_log_filename: t.Optional[str] = field(
        default=None,
        metadata=asdict(
            FieldMetadata(
                description='Log filename under the build directory instead of stdout. Can expand placeholders',
            )
        ),
    )
    size_file: t.Optional[str] = field(
        default=None,
        metadata=asdict(
            FieldMetadata(
                deprecated_by='size_json_filename',
            )
        ),
    )
    size_json_filename: t.Optional[str] = field(
        default=None,
        metadata=asdict(
            FieldMetadata(
                description='`idf.py size` output file under the build directory when specified. '
                'Can expand placeholders',
            )
        ),
    )
    config: t.Optional[t.List[str]] = field(
        default=None,
        metadata=asdict(
            FieldMetadata(
                deprecated_by='config_rules',
                nargs='+',
            )
        ),
    )
    config_rules_str: InitVar[t.Union[t.List[str], str, None]] = None
    config_rules: t.Optional[t.List[str]] = field(
        default=None,
        metadata=asdict(
            FieldMetadata(
                description='Defines the rules of building the project with pre-set sdkconfig files. '
                'Supports FILENAME[=NAME] or FILEPATTERN format. '
                'FILENAME is the filename of the sdkconfig file, relative to the app directory. '
                'Optional NAME is the name of the configuration. '
                'if not specified, the filename is used as the name. '
                'FILEPATTERN is the filename of the sdkconfig file with a single wildcard character (*). '
                'The NAME is the value matched by the wildcard',
                nargs='+',
            )
        ),
    )
    override_sdkconfig_items: t.Optional[str] = field(
        default=None,
        metadata=asdict(
            FieldMetadata(
                description='A comma-separated list of key=value pairs to override the sdkconfig items',
            )
        ),
    )
    override_sdkconfig_files: t.Optional[str] = field(
        default=None,
        metadata=asdict(
            FieldMetadata(
                description='A comma-separated list of sdkconfig files to override the sdkconfig items. '
                'When set to relative path, it will be treated as relative to the current directory',
            )
        ),
    )
    sdkconfig_defaults: t.Optional[str] = field(
        default=os.getenv('SDKCONFIG_DEFAULTS', None),
        metadata=asdict(
            FieldMetadata(
                description='A semicolon-separated list of sdkconfig files passed to `idf.py -DSDKCONFIG_DEFAULTS`. '
                'SDKCONFIG_DEFAULTS environment variable is used when not specified',
            )
        ),
    )
    check_warnings: bool = field(
        default=False,
        metadata=asdict(
            FieldMetadata(
                description='Check for warnings in the build output. Fail if any warnings are found',
                action='store_true',
            )
        ),
    )
    default_build_targets: t.Optional[t.List[str]] = field(
        default=None,
        metadata=asdict(
            FieldMetadata(
                description='space-separated list of the default enabled build targets for the apps. '
                'When not specified, the default value is the targets listed by `idf.py --list-targets`',
            )
        ),
    )
    enable_preview_targets: bool = field(
        default=False,
        metadata=asdict(
            FieldMetadata(
                description='When enabled, the default build targets will be set to all apps, '
                'including the preview targets. As the targets defined in `idf.py --list-targets --preview`',
                action='store_true',
            )
        ),
    )
    include_skipped_apps: bool = field(
        default=False,
        metadata=asdict(
            FieldMetadata(
                description='Include the skipped apps in the output, together with the enabled ones',
                action='store_true',
            )
        ),
    )
    include_disabled_apps: bool = field(
        default=False,
        metadata=asdict(
            FieldMetadata(
                description='Include the disabled apps in the output, together with the enabled ones',
                action='store_true',
            )
        ),
    )
    include_all_apps: bool = field(
        default=False,
        metadata=asdict(
            FieldMetadata(
                description='Include skipped, and disabled apps in the output, together with the enabled ones',
                action='store_true',
            )
        ),
    )

    def __post_init__(
        self,
        exclude_list: t.Optional[t.List[str]] = None,
        config_rules_str: t.Union[t.List[str], str, None] = None,
    ):
        super().__post_init__()

        self.paths = to_list(self.paths)
        self.config_rules = to_list(self.config_rules) or to_list(config_rules_str)
        self.exclude = self.exclude or exclude_list or []

        # Validation
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


@dataclass
class FindArguments(FindBuildArguments):
    """
    Arguments used in the find command
    """

    output: t.Optional[str] = field(
        default=None,
        metadata=asdict(
            FieldMetadata(
                description='Record the found apps to the specified file instead of stdout',
                shorthand='-o',
            )
        ),
    )
    output_format: str = field(
        default='raw',
        metadata=asdict(
            FieldMetadata(
                description='Output format of the found apps. '
                'In "raw" format, each line is a json string serialized from the app model. '
                'In "json" format, the output is a json list of the serialized app models',
                choices=['raw', 'json'],
            )
        ),
    )

    def __post_init__(
        self,
        exclude_list: t.Optional[t.List[str]] = None,
        config_rules_str: t.Union[t.List[str], str, None] = None,
    ):
        super().__post_init__(exclude_list, config_rules_str)

        if self.include_all_apps:
            self.include_skipped_apps = True
            self.include_disabled_apps = True

        if self.output and self.output.endswith('.json') and self.output_format in ['raw', None]:
            LOGGER.debug('Detecting output file ends with ".json", writing as json file.')
            self.output_format = 'json'


@dataclass
class BuildArguments(FindBuildArguments):
    build_verbose: bool = field(
        default=False,
        metadata=asdict(
            FieldMetadata(
                description='Enable verbose output of the build system',
                action='store_true',
            )
        ),
    )
    parallel_count: int = field(
        default=1,
        metadata=asdict(
            FieldMetadata(
                description='Number of parallel build jobs in total. '
                'Specified together with --parallel-index. '
                'The given apps will be divided into parallel_count parts, '
                'and the current run will build the parallel_index-th part',
                type=int,
            )
        ),
    )
    parallel_index: int = field(
        default=1,
        metadata=asdict(
            FieldMetadata(
                description='Index (1-based) of the parallel build job. '
                'Specified together with --parallel-count. '
                'The given apps will be divided into parallel_count parts, '
                'and the current run will build the parallel_index-th part',
                type=int,
            )
        ),
    )
    dry_run: bool = field(
        default=False,
        metadata=asdict(
            FieldMetadata(
                description='Skip the actual build, only print the build process',
                action='store_true',
            )
        ),
    )
    keep_going: bool = field(
        default=False,
        metadata=asdict(
            FieldMetadata(
                description='Continue building the next app when the current build fails',
                action='store_true',
            )
        ),
    )
    no_preserve: bool = field(
        default=False,
        metadata=asdict(
            FieldMetadata(
                description='Do not preserve the build directory after a successful build',
                action='store_true',
            )
        ),
    )
    collect_size_info: t.Optional[str] = field(
        default=None,
        metadata=asdict(
            FieldMetadata(
                description='[INTERNAL CI USE] record size json filepath of the built apps to the specified file. '
                'Each line is a json string. Can expand placeholders @p',
            )
        ),
    )
    collect_app_info: t.Optional[str] = field(
        default=None,
        metadata=asdict(
            FieldMetadata(
                description='[INTERNAL CI USE] record serialized app model of the built apps to the specified file. '
                'Each line is a json string. Can expand placeholders @p',
            )
        ),
    )
    ignore_warning_str: t.Optional[t.List[str]] = field(
        default=None,
        metadata=asdict(
            FieldMetadata(
                deprecated_by='ignore_warning_strings',
                nargs='+',
            )
        ),
    )
    ignore_warning_strings: t.Optional[t.List[str]] = field(
        default=None,
        metadata=asdict(
            FieldMetadata(
                description='space-separated list of patterns. '
                'Ignore the warnings in the build output that match the patterns',
                nargs='+',
            )
        ),
    )
    ignore_warning_file: t.Optional[str] = field(
        default=None,
        metadata=asdict(
            FieldMetadata(
                description='Path to the file containing the patterns to ignore the warnings in the build output',
                deprecated_by='ignore_warning_files',
            )
        ),
    )
    ignore_warning_files: t.Optional[t.List[str]] = field(
        default=None,
        metadata=asdict(
            FieldMetadata(
                description='Path to the files containing the patterns to ignore the warnings in the build output',
                nargs='+',
            )
        ),
    )
    copy_sdkconfig: bool = field(
        default=False,
        metadata=asdict(
            FieldMetadata(
                description='Copy the sdkconfig file to the build directory',
                action='store_true',
            )
        ),
    )
    junitxml: t.Optional[str] = field(
        default=None,
        metadata=asdict(
            FieldMetadata(
                description='Path to the junitxml file to record the build results. Can expand placeholder @p',
            )
        ),
    )

    def __post_init__(
        self,
        exclude_list: t.Optional[t.List[str]] = None,
        config_rules_str: t.Union[t.List[str], str, None] = None,
    ):
        super().__post_init__(exclude_list, config_rules_str)

        ignore_warnings_regexes = []
        if self.ignore_warning_strings:
            for s in self.ignore_warning_strings:
                ignore_warnings_regexes.append(re.compile(s))
        if self.ignore_warning_files:
            for s in self.ignore_warning_files:
                ignore_warnings_regexes.append(re.compile(s.strip()))
        App.IGNORE_WARNS_REGEXES = ignore_warnings_regexes


@dataclass
class DumpManifestShaArguments(GlobalArguments):
    """
    Arguments used in the dump-manifest-sha command
    """

    manifest_files: t.Optional[t.List[str]] = field(
        default=None,
        metadata=asdict(
            FieldMetadata(
                description='Path to the manifest files which contains the build test rules of the apps',
                nargs='+',
                required=True,
            )
        ),
    )
    output: t.Optional[str] = field(
        default=None,
        metadata=asdict(
            FieldMetadata(
                description='Record the sha256 hash of the manifest rules to the specified file',
                shorthand='-o',
                required=True,
            )
        ),
    )

    def __post_init__(self):
        super().__post_init__()

        # Validation
        self.manifest_files = to_list(self.manifest_files)
        if not self.manifest_files:
            raise InvalidCommand('Manifest files are required to dump the SHA values.')
        if not self.output:
            raise InvalidCommand('Output file is required to dump the SHA values.')


def add_arguments_to_parser(argument_cls: t.Type[GlobalArguments], parser: argparse.ArgumentParser) -> None:
    """
    Add arguments to the parser from the argument class.

    FieldMetadata is used to set the argparse options.

    :param argument_cls: argument class
    :param parser: argparse parser
    """
    name_fields_dict = {f.name: f for f in fields(argument_cls)}

    def _snake_case_to_cli_arg_name(s: str) -> str:
        return f'--{s.replace("_", "-")}'

    def _drop_none(d: dict) -> dict:
        return {k: v for k, v in d.items() if v is not None}

    for name, f in name_fields_dict.items():
        _meta = FieldMetadata(**f.metadata)

        desp = _meta.description
        if _meta.deprecated_by:
            if _meta.deprecated_by not in name_fields_dict:
                raise ValueError(f'{_meta.deprecated_by} not found in {argument_cls}')

            deprecated_by_field = name_fields_dict[_meta.deprecated_by]
            desp = desp or deprecated_by_field.metadata['description']
            desp = f'[DEPRECATED by {_snake_case_to_cli_arg_name(_meta.deprecated_by)}] {desp}'

        # args
        args = [_snake_case_to_cli_arg_name(name)]
        if _meta.shorthand:
            args.append(_meta.shorthand)

        # kwargs passed to add_argument
        kwargs = _drop_none(
            {
                'help': desp,
                'action': _meta.action,
                'nargs': _meta.nargs,
                'choices': _meta.choices,
                'type': _meta.type,
                'required': _meta.required,
            }
        )
        # default None is important for argparse
        kwargs['default'] = _meta.default or getattr(f, 'default', None)

        parser.add_argument(*args, **kwargs)


def add_arguments_to_obj_doc_as_params(argument_cls: t.Type[GlobalArguments], obj: t.Any = None) -> None:
    """
    Add arguments to the function as parameters.

    :param argument_cls: argument class
    :param obj: object to add the docstring to
    """
    _obj = obj or argument_cls
    _docs_s = _obj.__doc__ or ''
    _docs_s += '\n'

    for f in fields(argument_cls):
        if f.metadata.get('deprecated_by'):
            continue

        # typing generic alias is not a class
        _annotation = f.type.__name__ if inspect.isclass(f.type) else f.type

        _docs_s += f'    :param {f.name}: {f.metadata.get("description", "")}\n'
        _docs_s += f'    :type {f.name}: {_annotation}\n'

    _obj.__doc__ = _docs_s
