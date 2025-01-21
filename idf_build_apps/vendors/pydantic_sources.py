# SPDX-FileCopyrightText: 2022 Samuel Colvin and other contributors
# SPDX-License-Identifier: MIT

"""
Partially copied from https://github.com/pydantic/pydantic-settings v2.5.2
since python 3.7 version got dropped at pydantic-settings 2.1.0
but the feature we need introduced in 2.2.0

For contributing history please refer to the original github page
For the full license text refer to
https://github.com/pydantic/pydantic-settings/blob/9b73e924cab136d876907af0c6836dcca09ac35c/LICENSE

Modifications:
- use toml instead of tomli when python < 3.11
- stop using global variables
- fix some warnings
- recursively find TOML file.
"""

import logging
import os
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Type, Union

from pydantic_settings import InitSettingsSource
from pydantic_settings.main import BaseSettings

from idf_build_apps.constants import IDF_BUILD_APPS_TOML_FN

PathType = Union[Path, str, List[Union[Path, str]], Tuple[Union[Path, str], ...]]
DEFAULT_PATH = Path('')
LOGGER = logging.getLogger(__name__)


class ConfigFileSourceMixin(ABC):
    def _read_files(self, files: Optional[PathType]) -> Dict[str, Any]:
        if files is None:
            return {}
        if isinstance(files, (str, os.PathLike)):
            files = [files]
        kwargs: Dict[str, Any] = {}
        for file in files:
            file_path = Path(file).expanduser()
            if file_path.is_file():
                kwargs.update(self._read_file(file_path))
        return kwargs

    @abstractmethod
    def _read_file(self, path: Optional[Path]) -> Dict[str, Any]:
        pass


class TomlConfigSettingsSource(InitSettingsSource, ConfigFileSourceMixin):
    """
    A source class that loads variables from a TOML file
    """

    def __init__(
        self,
        settings_cls: Type[BaseSettings],
        toml_file: Optional[Path] = DEFAULT_PATH,
    ):
        self.toml_file_path = self._pick_toml_file(
            toml_file,
            settings_cls.model_config.get('pyproject_toml_depth', sys.maxsize),
            IDF_BUILD_APPS_TOML_FN,
        )
        self.toml_data = self._read_files(self.toml_file_path)
        super().__init__(settings_cls, self.toml_data)

    def _read_file(self, path: Optional[Path]) -> Dict[str, Any]:
        if not path or not path.is_file():
            return {}

        if sys.version_info < (3, 11):
            import toml

            with open(path) as toml_file:
                return toml.load(toml_file)
        else:
            import tomllib

            with open(path, 'rb') as toml_file:
                return tomllib.load(toml_file)

    @staticmethod
    def _pick_toml_file(provided: Optional[Path], depth: int, filename: str) -> Optional[Path]:
        """
        Pick a file path to use. If a file path is provided, use it. Otherwise, search up the directory tree for a
        file with the given name.

        :param provided: Explicit path provided when instantiating this class.
        :param depth: Number of directories up the tree to check of a pyproject.toml.
        """
        if provided and Path(provided).is_file():
            fp = provided.resolve()
            LOGGER.debug(f'Loading config file: {fp}')
            return fp

        rv = Path.cwd()
        count = -1
        while count < depth:
            if len(rv.parts) == 1:
                break

            fp = rv / filename
            if fp.is_file():
                LOGGER.debug(f'Loading config file: {fp}')
                return fp

            rv = rv.parent
            count += 1

        return None


class PyprojectTomlConfigSettingsSource(TomlConfigSettingsSource):
    """
    A source class that loads variables from a `pyproject.toml` file.
    """

    def __init__(
        self,
        settings_cls: Type[BaseSettings],
        toml_file: Optional[Path] = None,
    ) -> None:
        self.toml_file_path = self._pick_toml_file(
            toml_file,
            settings_cls.model_config.get('pyproject_toml_depth', sys.maxsize),
            'pyproject.toml',
        )
        self.toml_table_header: Tuple[str, ...] = settings_cls.model_config.get(
            'pyproject_toml_table_header',
            ('tool', 'idf-build-apps'),
        )
        self.toml_data = self._read_files(self.toml_file_path)
        for key in self.toml_table_header:
            self.toml_data = self.toml_data.get(key, {})
        super(TomlConfigSettingsSource, self).__init__(settings_cls, self.toml_data)
