# SPDX-FileCopyrightText: 2022-2023 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import enum
import importlib
import logging
import os
import re
import sys
import tempfile
import typing as t
from pathlib import (
    Path,
)

from .utils import (
    to_version,
)

LOGGER = logging.getLogger(__name__)

_BUILDING_DOCS = bool(os.getenv('BUILDING_DOCS'))
if _BUILDING_DOCS:
    print('Building Docs... Faking lots of constant values')


if _BUILDING_DOCS:
    _idf_env = tempfile.gettempdir()
else:
    _idf_env = os.getenv('IDF_PATH', '')
if not os.path.isdir(_idf_env):
    raise ValueError(f'Invalid value for IDF_PATH: {_idf_env}')


IDF_PATH = Path(_idf_env).resolve()
IDF_PY = IDF_PATH / 'tools' / 'idf.py'
IDF_SIZE_PY = IDF_PATH / 'tools' / 'idf_size.py'
PROJECT_DESCRIPTION_JSON = 'project_description.json'
DEFAULT_SDKCONFIG = 'sdkconfig.defaults'


sys.path.append(str(IDF_PATH / 'tools' / 'idf_py_actions'))
if _BUILDING_DOCS:
    _idf_py_constant_py = object()
else:
    try:
        _idf_py_constant_py = importlib.import_module('constants')
    except ModuleNotFoundError:
        LOGGER.warning('Cannot import constants from idf_py_actions')
        _idf_py_constant_py = object()
SUPPORTED_TARGETS = getattr(_idf_py_constant_py, 'SUPPORTED_TARGETS', [])
PREVIEW_TARGETS = getattr(_idf_py_constant_py, 'PREVIEW_TARGETS', [])
ALL_TARGETS = SUPPORTED_TARGETS + PREVIEW_TARGETS


def _idf_version_from_cmake() -> t.Tuple[int, int, int]:
    version_path = str(IDF_PATH / 'tools' / 'cmake' / 'version.cmake')
    if not os.path.isfile(version_path):
        raise ValueError(f'File {version_path} does not exist')

    regex = re.compile(r'^\s*set\s*\(\s*IDF_VERSION_([A-Z]{5})\s+(\d+)')
    ver = {}
    try:
        with open(version_path) as f:
            for line in f:
                m = regex.match(line)

                if m:
                    ver[m.group(1)] = m.group(2)

        return int(ver['MAJOR']), int(ver['MINOR']), int(ver['PATCH'])
    except (KeyError, OSError):
        raise ValueError(f'Cannot find ESP-IDF version in {version_path}')


if _BUILDING_DOCS:
    IDF_VERSION_MAJOR, IDF_VERSION_MINOR, IDF_VERSION_PATCH = 1, 0, 0
else:
    IDF_VERSION_MAJOR, IDF_VERSION_MINOR, IDF_VERSION_PATCH = _idf_version_from_cmake()

IDF_VERSION = to_version(f'{IDF_VERSION_MAJOR}.{IDF_VERSION_MINOR}.{IDF_VERSION_PATCH}')


class BuildStatus(str, enum.Enum):
    UNKNOWN = 'unknown'
    SKIPPED = 'skipped'
    SHOULD_BE_BUILT = 'should be built'
    FAILED = 'build failed'
    SUCCESS = 'build success'


class BuildStage(str, enum.Enum):
    DRY_RUN = 'Dry Run'
    PRE_BUILD = 'Pre Build'
    BUILD = 'Build'
    POST_BUILD = 'Post Build'

    @classmethod
    def max_length(cls) -> int:
        return max(len(v.value) for v in cls.__members__.values())
