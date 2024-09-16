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
from copy import deepcopy
from dataclasses import InitVar, asdict, dataclass, field, fields
from enum import Enum

from . import SESSION_ARGS, setup_logging
from .app import App
from .config import get_valid_config
from .constants import ALL_TARGETS
from .manifest.manifest import FolderRule, Manifest
from .utils import (
    InvalidCommand,
    Self,
    drop_none_kwargs,
    files_matches_patterns,
    semicolon_separated_str_to_list,
    to_absolute_path,
    to_list,
)

LOGGER = logging.getLogger(__name__)


class _Field(Enum):
    UNSET = 'UNSET'


@dataclass
class FieldMetadata:
    """
    dataclass field metadata. All fields are optional.
    Some fields are used in argparse while running :func:`add_args_to_parser`.

    :param description: description of the field
    :param deprecates: deprecates field names, used in argparse
    :param shorthand: shorthand for the argument, used in argparse
    :param action: action for the argument, used in argparse
    :param nargs: nargs for the argument, used in argparse
    :param choices: choices for the argument, used in argparse
    :param type: type for the argument, used in argparse
    :param required: whether the argument is required, used in argparse
    :param default: default value, used in argparse
    """

    description: t.Optional[str] = None
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

    _depr_name_to_new_name_dict: t.ClassVar[t.Dict[str, str]] = {}  # record deprecated field <-> new field

    def __new__(cls, *args, **kwargs):  # noqa: ARG003
        for f in fields(cls):
            _metadata = FieldMetadata(**f.metadata)
            if _metadata.deprecates:
                for depr_name in _metadata.deprecates:
                    cls._depr_name_to_new_name_dict[depr_name] = f.name

        return super().__new__(cls)

    @classmethod
    def from_dict(cls, d: t.Dict[str, t.Any]) -> Self:
        """
        Create an instance from a dictionary. Ignore unknown keys.

        :param d: dictionary
        :return: instance
        """
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    def __post_init__(self):
        self.apply_config()

    def apply_config(self) -> None:
        """
        Apply the configuration file to the arguments
        """
        config_dict = get_valid_config(custom_path=self.config_file) or {}

        # set log fields first
        self.verbose = config_dict.pop('verbose', self.verbose)
        self.log_file = config_dict.pop('log_file', self.log_file)
        self.no_color = config_dict.pop('no_color', self.no_color)
        setup_logging(self.verbose, self.log_file, not self.no_color)

        if config_dict:
            for name, value in config_dict.items():
                if hasattr(self, name):
                    setattr(self, name, value)

                if name in self._depr_name_to_new_name_dict:
                    self.set_deprecated_field(self._depr_name_to_new_name_dict[name], name, value)

    def set_deprecated_field(self, new_k: str, depr_k: str, depr_v: t.Any) -> None:
        if depr_v == _Field.UNSET:
            return

        LOGGER.warning(
            f'Field `{depr_k}` is deprecated. Will be removed in the next major release. '
            f'Use field `{new_k}` instead.'
        )
        if getattr(self, new_k) is not None:
            LOGGER.warning(f'Field `{new_k}` is already set. Ignoring deprecated field `{depr_k}`')
            return

        setattr(self, new_k, depr_v)


@dataclass
class DependencyDrivenBuildArguments(GlobalArguments):
    """
    Arguments used in the dependency-driven build feature.
    """

    manifest_file: InitVar[t.Optional[t.List[str]]] = _Field.UNSET
    manifest_files: t.Optional[t.List[str]] = field(
        default=None,
        metadata=asdict(
            FieldMetadata(
                deprecates={
                    'manifest_file': {
                        'nargs': '+',
                    },
                },
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
    ignore_app_dependencies_components: InitVar[t.Optional[t.List[str]]] = _Field.UNSET
    deactivate_dependency_driven_build_by_components: t.Optional[t.List[str]] = field(
        default=None,
        metadata=asdict(
            FieldMetadata(
                deprecates={
                    'ignore_app_dependencies_components': {
                        'type': semicolon_separated_str_to_list,
                        'shorthand': '-ic',
                    }
                },
                description='semicolon-separated list of components. '
                'dependency-driven build feature will be deactivated when any of these components are modified',
                type=semicolon_separated_str_to_list,
                shorthand='-dc',
            )
        ),
    )
    ignore_app_dependencies_filepatterns: InitVar[t.Optional[t.List[str]]] = _Field.UNSET
    deactivate_dependency_driven_build_by_filepatterns: t.Optional[t.List[str]] = field(
        default=None,
        metadata=asdict(
            FieldMetadata(
                deprecates={
                    'ignore_app_dependencies_filepatterns': {
                        'type': semicolon_separated_str_to_list,
                        'shorthand': '-if',
                    }
                },
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

    def __post_init__(
        self,
        manifest_file: t.Optional[t.List[str]] = _Field.UNSET,  # type: ignore
        ignore_app_dependencies_components: t.Optional[t.List[str]] = _Field.UNSET,  # type: ignore
        ignore_app_dependencies_filepatterns: t.Optional[t.List[str]] = _Field.UNSET,  # type: ignore
    ):
        super().__post_init__()

        self.set_deprecated_field('manifest_files', 'manifest_file', manifest_file)
        self.set_deprecated_field(
            'deactivate_dependency_driven_build_by_components',
            'ignore_app_dependencies_components',
            ignore_app_dependencies_components,
        )
        self.set_deprecated_field(
            'deactivate_dependency_driven_build_by_filepatterns',
            'ignore_app_dependencies_filepatterns',
            ignore_app_dependencies_filepatterns,
        )

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
    exclude_list: InitVar[t.Optional[t.List[str]]] = _Field.UNSET
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
    build_log: InitVar[t.Optional[str]] = _Field.UNSET
    build_log_filename: t.Optional[str] = field(
        default=None,
        metadata=asdict(
            FieldMetadata(
                deprecates={'build_log': {}},
                description='Log filename under the build directory instead of stdout. Can expand placeholders',
            )
        ),
    )
    size_file: InitVar[t.Optional[str]] = _Field.UNSET
    size_json_filename: t.Optional[str] = field(
        default=None,
        metadata=asdict(
            FieldMetadata(
                deprecates={'size_file': {}},
                description='`idf.py size` output file under the build directory when specified. '
                'Can expand placeholders',
            )
        ),
    )
    config: InitVar[t.Union[t.List[str], str, None]] = _Field.UNSET  # cli  # type: ignore
    config_rules_str: InitVar[t.Union[t.List[str], str, None]] = _Field.UNSET  # func  # type: ignore
    config_rules: t.Optional[t.List[str]] = field(
        default=None,
        metadata=asdict(
            FieldMetadata(
                deprecates={
                    'config': {'nargs': '+'},
                },
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

    def __post_init__(  # type: ignore
        self,
        manifest_file: t.Optional[t.List[str]] = _Field.UNSET,  # type: ignore
        ignore_app_dependencies_components: t.Optional[t.List[str]] = _Field.UNSET,  # type: ignore
        ignore_app_dependencies_filepatterns: t.Optional[t.List[str]] = _Field.UNSET,  # type: ignore
        exclude_list: t.Optional[t.List[str]] = _Field.UNSET,  # type: ignore
        build_log: t.Optional[str] = _Field.UNSET,  # type: ignore
        size_file: t.Optional[str] = _Field.UNSET,  # type: ignore
        config: t.Optional[t.List[str]] = _Field.UNSET,  # type: ignore
        config_rules_str: t.Union[t.List[str], str, None] = _Field.UNSET,  # type: ignore
    ):
        super().__post_init__(
            manifest_file=manifest_file,
            ignore_app_dependencies_components=ignore_app_dependencies_components,
            ignore_app_dependencies_filepatterns=ignore_app_dependencies_filepatterns,
        )

        self.set_deprecated_field('exclude', 'exclude_list', exclude_list)
        self.set_deprecated_field('build_log_filename', 'build_log', build_log)
        self.set_deprecated_field('size_json_filename', 'size_file', size_file)
        self.set_deprecated_field('config_rules', 'config', config)
        self.set_deprecated_field('config_rules', 'config_rules_str', config_rules_str)

        self.paths = to_list(self.paths)
        self.config_rules = to_list(self.config_rules)
        self.exclude = to_list(self.exclude)

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

    def __post_init__(  # type: ignore
        self,
        manifest_file: t.Optional[t.List[str]] = _Field.UNSET,  # type: ignore
        ignore_app_dependencies_components: t.Optional[t.List[str]] = _Field.UNSET,  # type: ignore
        ignore_app_dependencies_filepatterns: t.Optional[t.List[str]] = _Field.UNSET,  # type: ignore
        exclude_list: t.Optional[t.List[str]] = _Field.UNSET,  # type: ignore
        build_log: t.Optional[str] = _Field.UNSET,  # type: ignore
        size_file: t.Optional[str] = _Field.UNSET,  # type: ignore
        config: t.Optional[t.List[str]] = _Field.UNSET,  # type: ignore
        config_rules_str: t.Union[t.List[str], str, None] = _Field.UNSET,  # type: ignore
    ):
        super().__post_init__(
            manifest_file=manifest_file,
            ignore_app_dependencies_components=ignore_app_dependencies_components,
            ignore_app_dependencies_filepatterns=ignore_app_dependencies_filepatterns,
            exclude_list=exclude_list,
            build_log=build_log,
            size_file=size_file,
            config=config,
            config_rules_str=config_rules_str,
        )

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
                description='Record size json filepath of the built apps to the specified file. '
                'Each line is a json string. Can expand placeholders @p',
            )
        ),
    )
    _collect_size_info: t.Optional[str] = field(init=False, repr=False, default=None)
    collect_app_info: t.Optional[str] = field(
        default=None,
        metadata=asdict(
            FieldMetadata(
                description='Record serialized app model of the built apps to the specified file. '
                'Each line is a json string. Can expand placeholders @p',
            )
        ),
    )
    _collect_app_info: t.Optional[str] = field(init=False, repr=False, default=None)
    ignore_warning_str: InitVar[t.Optional[t.List[str]]] = _Field.UNSET
    ignore_warning_strs: t.Optional[t.List[str]] = field(
        default=None,
        metadata=asdict(
            FieldMetadata(
                deprecates={
                    'ignore_warning_str': {'nargs': '+'},
                },
                description='space-separated list of patterns. '
                'Ignore the warnings in the build output that match the patterns',
                nargs='+',
            )
        ),
    )
    ignore_warning_file: InitVar[t.Optional[str]] = _Field.UNSET
    ignore_warning_files: t.Optional[t.List[str]] = field(
        default=None,
        metadata=asdict(
            FieldMetadata(
                deprecates={'ignore_warning_file': {}},
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
    _junitxml: t.Optional[str] = field(init=False, repr=False, default=None)

    # used for expanding placeholders
    PARALLEL_INDEX_PLACEHOLDER: t.ClassVar[str] = '@p'  # replace it with the parallel index

    def __post_init__(  # type: ignore
        self,
        manifest_file: t.Optional[t.List[str]] = _Field.UNSET,  # type: ignore
        ignore_app_dependencies_components: t.Optional[t.List[str]] = _Field.UNSET,  # type: ignore
        ignore_app_dependencies_filepatterns: t.Optional[t.List[str]] = _Field.UNSET,  # type: ignore
        exclude_list: t.Optional[t.List[str]] = _Field.UNSET,  # type: ignore
        build_log: t.Optional[str] = _Field.UNSET,  # type: ignore
        size_file: t.Optional[str] = _Field.UNSET,  # type: ignore
        config: t.Optional[t.List[str]] = _Field.UNSET,  # type: ignore
        config_rules_str: t.Union[t.List[str], str, None] = _Field.UNSET,  # type: ignore
        ignore_warning_str: t.Optional[t.List[str]] = _Field.UNSET,  # type: ignore
        ignore_warning_file: t.Optional[str] = _Field.UNSET,  # type: ignore
    ):
        super().__post_init__(
            manifest_file=manifest_file,
            ignore_app_dependencies_components=ignore_app_dependencies_components,
            ignore_app_dependencies_filepatterns=ignore_app_dependencies_filepatterns,
            exclude_list=exclude_list,
            build_log=build_log,
            size_file=size_file,
            config=config,
            config_rules_str=config_rules_str,
        )

        self.set_deprecated_field('ignore_warning_strs', 'ignore_warning_str', ignore_warning_str)
        self.set_deprecated_field('ignore_warning_files', 'ignore_warning_file', ignore_warning_file)

        self.ignore_warning_strs = to_list(self.ignore_warning_strs) or []

        ignore_warnings_regexes = []
        if self.ignore_warning_strs:
            for s in self.ignore_warning_strs:
                ignore_warnings_regexes.append(re.compile(s))
        if self.ignore_warning_files:
            for s in self.ignore_warning_files:
                ignore_warnings_regexes.append(re.compile(s.strip()))
        App.IGNORE_WARNS_REGEXES = ignore_warnings_regexes

        if not isinstance(BuildArguments.collect_size_info, property):
            self._collect_size_info = self.collect_size_info
            BuildArguments.collect_size_info = property(  # type: ignore
                BuildArguments._get_collect_size_info,
                BuildArguments._set_collect_size_info,
            )

        if not isinstance(BuildArguments.collect_app_info, property):
            self._collect_app_info = self.collect_app_info
            BuildArguments.collect_app_info = property(  # type: ignore
                BuildArguments._get_collect_app_info,
                BuildArguments._set_collect_app_info,
            )

        if not isinstance(BuildArguments.junitxml, property):
            self._junitxml = self.junitxml
            BuildArguments.junitxml = property(  # type: ignore
                BuildArguments._get_junitxml,
                BuildArguments._set_junitxml,
            )

    def _get_collect_size_info(self) -> t.Optional[str]:
        return (
            self._collect_size_info.replace(self.PARALLEL_INDEX_PLACEHOLDER, str(self.parallel_index))
            if self._collect_size_info
            else None
        )

    def _set_collect_size_info(self, k: str) -> None:
        self._collect_size_info = k

    def _get_collect_app_info(self) -> t.Optional[str]:
        return (
            self._collect_app_info.replace(self.PARALLEL_INDEX_PLACEHOLDER, str(self.parallel_index))
            if self._collect_app_info
            else None
        )

    def _set_collect_app_info(self, k: str) -> None:
        self._collect_app_info = k

    def _get_junitxml(self) -> t.Optional[str]:
        return (
            self._junitxml.replace(self.PARALLEL_INDEX_PLACEHOLDER, str(self.parallel_index))
            if self._junitxml
            else None
        )

    def _set_junitxml(self, k: str) -> None:
        self._junitxml = k


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

    for name, f in name_fields_dict.items():
        _meta = FieldMetadata(**f.metadata)

        desp = _meta.description
        # add deprecated fields
        if _meta.deprecates:
            for depr_k, depr_kwargs in _meta.deprecates.items():
                depr_kwargs['help'] = f'[DEPRECATED by {_snake_case_to_cli_arg_name(name)}] {desp}'
                short_name = depr_kwargs.pop('shorthand', None)
                _names = [_snake_case_to_cli_arg_name(depr_k)]
                if short_name:
                    _names.append(short_name)
                parser.add_argument(*_names, **depr_kwargs)

        # args
        args = [_snake_case_to_cli_arg_name(name)]
        if _meta.shorthand:
            args.append(_meta.shorthand)

        # kwargs passed to add_argument
        kwargs = drop_none_kwargs(
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
        # typing generic alias is not a class
        _annotation = f.type.__name__ if inspect.isclass(f.type) else f.type

        _docs_s += f'    :param {f.name}: {f.metadata.get("description", "")}\n'
        _docs_s += f'    :type {f.name}: {_annotation}\n'

    _obj.__doc__ = _docs_s
