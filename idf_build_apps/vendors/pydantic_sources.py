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
import sys
from pathlib import Path
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple
from typing import Type
from typing import Union

from pydantic_settings import BaseSettings
from pydantic_settings import InitSettingsSource
from pydantic_settings.sources import ConfigFileSourceMixin

from idf_build_apps.constants import IDF_BUILD_APPS_TOML_FN

PathType = Union[Path, str, List[Union[Path, str]], Tuple[Union[Path, str], ...]]
DEFAULT_PATH = Path('')
LOGGER = logging.getLogger(__name__)


class TomlConfigSettingsSource(InitSettingsSource, ConfigFileSourceMixin):
    """
    A source class that loads variables from a TOML file
    """

    def __init__(
        self,
        settings_cls: Type[BaseSettings],
        toml_file: Optional[Path] = DEFAULT_PATH,
        search_depth: int = sys.maxsize,
    ):
        self.toml_file_path = self._pick_toml_file(
            toml_file,
            search_depth,
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
        search_depth: int = sys.maxsize,
        table_header: Tuple[str, ...] = ('tool', 'idf-build-apps'),
    ) -> None:
        self.toml_file_path = self._pick_toml_file(
            toml_file,
            search_depth,
            'pyproject.toml',
        )
        self.toml_table_header = table_header
        self.toml_data = self._read_files(self.toml_file_path)
        for key in self.toml_table_header:
            self.toml_data = self.toml_data.get(key, {})
        super(TomlConfigSettingsSource, self).__init__(settings_cls, self.toml_data)
