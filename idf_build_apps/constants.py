# SPDX-FileCopyrightText: 2022 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import importlib
import os
import sys
from pathlib import Path

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
