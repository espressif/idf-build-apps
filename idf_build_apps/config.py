# SPDX-FileCopyrightText: 2023 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import os
import typing as t
from pathlib import (
    Path,
)

from idf_build_apps.utils import (
    to_absolute_path,
)


class InvalidTomlError(SystemExit):
    def __init__(self, filepath: t.Union[str, Path], msg: str) -> None:
        super().__init__(f'Failed parsing toml file "{filepath}" with error: {msg}')


PYPROJECT_TOML_FN = 'pyproject.toml'
IDF_BUILD_APPS_TOML_FN = '.idf_build_apps.toml'


def load_toml(filepath: t.Union[str, Path]) -> dict:
    try:
        import tomllib  # type: ignore # python 3.11

        try:
            with open(str(filepath), 'rb') as fr:
                return tomllib.load(fr)
        except Exception as e:
            raise InvalidTomlError(filepath, str(e))
    except ImportError:
        import toml

        try:
            return toml.load(str(filepath))
        except Exception as e:
            raise InvalidTomlError(filepath, str(e))


def _get_config_from_file(filepath: Path) -> t.Tuple[t.Optional[dict], Path]:
    config = None
    if filepath.is_file():
        if filepath.parts[-1] == PYPROJECT_TOML_FN:
            tool = load_toml(filepath).get('tool', None)
            if tool:
                config = tool.get('idf-build-apps', None)
        elif config is None:
            config = load_toml(filepath)

    return config, filepath


def _get_config_from_path(dirpath: Path) -> t.Tuple[t.Optional[dict], Path]:
    config = None
    filepath = dirpath
    if (dirpath / PYPROJECT_TOML_FN).is_file():
        config, filepath = _get_config_from_file(dirpath / PYPROJECT_TOML_FN)

    if config is None and (dirpath / IDF_BUILD_APPS_TOML_FN).is_file():
        config, filepath = _get_config_from_file(dirpath / IDF_BUILD_APPS_TOML_FN)

    return config, filepath


def get_valid_config(starts_from: str = os.getcwd(), custom_path: t.Optional[str] = None) -> t.Optional[dict]:
    root_dir = to_absolute_path('/')
    cur_dir = to_absolute_path(starts_from)

    config = None
    if custom_path and os.path.isfile(custom_path):
        config, filepath = _get_config_from_file(to_absolute_path(custom_path))
        if config is not None:
            # use print here since the verbose settings may be set in the config file
            print(f'Using custom config file: {filepath}')
            return config

    while cur_dir != root_dir and config is None:
        config, filepath = _get_config_from_path(cur_dir)
        if config is not None:
            # use print here since the verbose settings may be set in the config file
            print(f'Using config file: {filepath}')
            return config

        if (cur_dir / '.git').exists():
            break

        cur_dir = cur_dir.parent

    return None
