# SPDX-FileCopyrightText: 2023 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import os
from pathlib import (
    Path,
)


class InvalidTomlError(SystemExit):
    def __init__(self, filepath, msg):  # type: (str | Path, str) -> None
        super().__init__('Failed parsing toml file "{}" with error: {}'.format(filepath, msg))


PYPROJECT_TOML_FN = 'pyproject.toml'
IDF_BUILD_APPS_TOML_FN = '.idf_build_apps.toml'


def load_toml(filepath):  # type: (str | Path) -> dict
    try:
        import tomllib  # python 3.11

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


def _get_config_from_file(filepath):  # type: (Path) -> (dict | None, Path)
    config = None
    if filepath.is_file():
        if filepath.parts[-1] == PYPROJECT_TOML_FN:
            tool = load_toml(filepath).get('tool', None)
            if tool:
                config = tool.get('idf-build-apps', None)
        elif config is None:
            config = load_toml(filepath)

    return config, filepath


def _get_config_from_path(dirpath):  # type: (Path) -> (dict | None, Path)
    config = None
    filepath = dirpath
    if (dirpath / PYPROJECT_TOML_FN).is_file():
        config, filepath = _get_config_from_file(dirpath / PYPROJECT_TOML_FN)

    if config is None and (dirpath / IDF_BUILD_APPS_TOML_FN).is_file():
        config, filepath = _get_config_from_file(dirpath / IDF_BUILD_APPS_TOML_FN)

    return config, filepath


def get_valid_config(starts_from=os.getcwd(), custom_path=None):  # type: (str, str | None) -> dict | None
    root_dir = Path('/').resolve()
    cur_dir = Path(os.path.expanduser(starts_from)).resolve()

    config = None
    if custom_path and os.path.isfile(custom_path):
        config, filepath = _get_config_from_file(Path(os.path.expanduser(custom_path)).resolve())
        if config is not None:
            # use print here since the verbose settings may be set in the config file
            print('Using custom config file: {}'.format(filepath))
            return config

    while cur_dir != root_dir and config is None:
        config, filepath = _get_config_from_path(cur_dir)
        if config is not None:
            # use print here since the verbose settings may be set in the config file
            print('Using config file: {}'.format(filepath))
            return config

        if (cur_dir / '.git').exists():
            break

        cur_dir = cur_dir.parent

    return None
