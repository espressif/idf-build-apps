# SPDX-FileCopyrightText: 2023 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import os
import typing as t
from copy import (
    deepcopy,
)

from pydantic import (
    BaseModel,
    ConfigDict,
    computed_field,
    field_validator,
)

from . import (
    LOGGER,
    Manifest,
)
from .constants import (
    DEFAULT_SDKCONFIG,
    SUPPORTED_TARGETS,
)
from .utils import (
    files_matches_patterns,
    to_absolute_path,
    to_list,
)


class _GlobalConfig(BaseModel):
    """
    Global configuration for idf_build_apps. Session-wide.

    .. warning::

        This class cannot be serialized.
    """

    model_config = ConfigDict(
        validate_assignment=True,
        arbitrary_types_allowed=True,
    )

    rootpath: str = os.curdir
    manifest_rootpath: str = os.curdir

    manifest: t.Optional[Manifest] = None
    modified_components: t.Optional[t.Set[str]] = None
    modified_files: t.Optional[t.Set[str]] = None
    ignore_app_dependencies_filepatterns: t.Optional[t.Set[str]] = None

    default_sdkconfig_defaults: t.List[str] = [DEFAULT_SDKCONFIG]
    default_build_targets: t.List[str] = SUPPORTED_TARGETS

    @field_validator('modified_components', 'modified_files', 'ignore_app_dependencies_filepatterns', mode='before')
    def to_set(cls, v: t.Union[t.Iterable[str], str, None]) -> t.Optional[t.Set[str]]:
        if v is None:
            return v

        return set(to_list(v))

    @field_validator('default_sdkconfig_defaults', mode='before')
    def _get_sdkconfig_defaults(cls, v: t.Union[t.List[str], str, None] = None) -> t.List[str]:
        if isinstance(v, str):
            return v.split(';')

        if isinstance(v, list):
            return v

        if os.getenv('SDKCONFIG_DEFAULTS', None) is not None:
            return os.getenv('SDKCONFIG_DEFAULTS', None).split(';')

        return [DEFAULT_SDKCONFIG]

    @computed_field
    @property
    def check_app_dependencies(self) -> bool:
        """
        Check app dependencies while finding and building apps or not.

        :return: True if check app dependencies, otherwise False.
        """
        # not check since modified_components and modified_files are not passed
        if self.modified_components is None and self.modified_files is None:
            return False

        # not check since ignore_app_dependencies_filepatterns is passed and matched
        if (
            self.ignore_app_dependencies_filepatterns
            and self.modified_files is not None
            and self.matches_modified_files(self.ignore_app_dependencies_filepatterns)
        ):
            LOGGER.debug(
                'Skipping check component dependencies for apps since files %s matches patterns: %s',
                ', '.join(self.modified_files),
                ', '.join(self.ignore_app_dependencies_filepatterns),
            )
            return False

        return True

    def matches_modified_files(
        self,
        patterns: t.Iterable[str],
    ) -> bool:
        if not self.modified_files:
            return False

        return files_matches_patterns(
            files=self.modified_files,
            patterns=patterns,
            rootpath=self.rootpath,
        )

    def reset_and_config(
        self,
        default_build_targets: t.Union[t.Iterable[str], str, None] = None,
        default_sdkconfig_defaults: t.Optional[str] = None,
        # manifest files ones
        manifest_rootpath: t.Optional[str] = None,
        manifest_files: t.Union[t.Iterable[str], str, None] = None,
        # check app dependency ones
        modified_components: t.Union[t.Iterable[str], str, None] = None,
        modified_files: t.Union[t.Iterable[str], str, None] = None,
        ignore_app_dependencies_filepatterns: t.Union[t.Iterable[str], str, None] = None,
    ) -> None:
        """
        Reset global settings and configure them.
        """
        self.default_build_targets = SUPPORTED_TARGETS
        if default_build_targets is not None:
            self.default_build_targets = to_list(default_build_targets)
            LOGGER.info('Overriding DEFAULT_BUILD_TARGETS to %s', self.default_build_targets)

        self.default_sdkconfig_defaults = default_sdkconfig_defaults

        self.manifest_rootpath = str(to_absolute_path(manifest_rootpath or os.curdir))
        self.rootpath = deepcopy(self.manifest_rootpath)

        self.manifest = None
        if manifest_files is not None:
            rules = set()
            for _manifest_file in to_list(manifest_files):
                LOGGER.debug('Loading manifest file: %s', _manifest_file)
                rules.update(Manifest.from_file(_manifest_file).rules)
            manifest = Manifest(rules)
            self.manifest = manifest

        self.modified_components = None
        if modified_components is not None:
            self.modified_components = modified_components

        self.modified_files = None
        if modified_files is not None:
            self.modified_files = modified_files

        self.ignore_app_dependencies_filepatterns = None
        if ignore_app_dependencies_filepatterns is not None:
            self.ignore_app_dependencies_filepatterns = ignore_app_dependencies_filepatterns
