# SPDX-FileCopyrightText: 2022-2023 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import importlib
import os
import re
import sys
import tempfile
from pathlib import (
    Path,
)

from packaging.version import (
    Version,
)

_BUILDING_DOCS = bool(os.getenv('BUILDING_DOCS'))
if _BUILDING_DOCS:
    print('Building Docs... Faking lots of constant values')


if _BUILDING_DOCS:
    _idf_env = tempfile.gettempdir()
else:
    _idf_env = os.getenv('IDF_PATH', '')
if not os.path.isdir(_idf_env):
    raise ValueError('Invalid value for IDF_PATH: {}'.format(_idf_env))


IDF_PATH = Path(_idf_env).resolve()
IDF_PY = IDF_PATH / 'tools' / 'idf.py'
IDF_SIZE_PY = IDF_PATH / 'tools' / 'idf_size.py'
PROJECT_DESCRIPTION_JSON = 'project_description.json'
DEFAULT_SDKCONFIG = 'sdkconfig.defaults'


sys.path.append(str(IDF_PATH / 'tools' / 'idf_py_actions'))
if _BUILDING_DOCS:
    _idf_py_constant_py = object()
else:
    _idf_py_constant_py = importlib.import_module('constants')
SUPPORTED_TARGETS = getattr(_idf_py_constant_py, 'SUPPORTED_TARGETS', [])
PREVIEW_TARGETS = getattr(_idf_py_constant_py, 'PREVIEW_TARGETS', [])
ALL_TARGETS = SUPPORTED_TARGETS + PREVIEW_TARGETS


def _idf_version_from_cmake():  # type: () -> (int, int, int)
    version_path = str(IDF_PATH / 'tools' / 'cmake' / 'version.cmake')
    if not os.path.isfile(version_path):
        raise ValueError('File {} does not exist'.format(version_path))

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
        raise ValueError('Cannot find ESP-IDF version in {}'.format(version_path))


if _BUILDING_DOCS:
    IDF_VERSION_MAJOR, IDF_VERSION_MINOR, IDF_VERSION_PATCH = 1, 0, 0
else:
    IDF_VERSION_MAJOR, IDF_VERSION_MINOR, IDF_VERSION_PATCH = _idf_version_from_cmake()

IDF_VERSION = Version('{}.{}.{}'.format(IDF_VERSION_MAJOR, IDF_VERSION_MINOR, IDF_VERSION_PATCH))
