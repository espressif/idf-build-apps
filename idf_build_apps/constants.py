# SPDX-FileCopyrightText: 2022 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import importlib
import os
import re
import sys
from pathlib import Path

from packaging.version import Version

_idf_env = os.getenv('IDF_PATH', '')
if not os.path.isdir(_idf_env):
    raise ValueError('Invalid value for IDF_PATH: {}'.format(_idf_env))

IDF_PATH = Path(_idf_env).resolve()
IDF_PY = IDF_PATH / 'tools' / 'idf.py'
IDF_SIZE_PY = IDF_PATH / 'tools' / 'idf_size.py'

sys.path.append(str(IDF_PATH / 'tools' / 'idf_py_actions'))
_idf_py_constant_py = importlib.import_module('constants')

SUPPORTED_TARGETS = getattr(_idf_py_constant_py, 'SUPPORTED_TARGETS', [])
PREVIEW_TARGETS = getattr(_idf_py_constant_py, 'PREVIEW_TARGETS', [])
ALL_TARGETS = SUPPORTED_TARGETS + PREVIEW_TARGETS


def _idf_version_from_cmake():
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

        return Version('{}.{}.{}'.format(ver['MAJOR'], ver['MINOR'], ver['PATCH']))
    except (KeyError, OSError):
        raise ValueError('Cannot find ESP-IDF version in {}'.format(version_path))


IDF_VERSION = _idf_version_from_cmake()
