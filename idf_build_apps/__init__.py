# SPDX-FileCopyrightText: 2022-2023 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

"""
Tools for building ESP-IDF related apps.
"""

# ruff: noqa: E402
# need this to avoid circular imports

import logging

__version__ = '1.0.2'


LOGGER = logging.getLogger('idf_build_apps')

# isort: off
from .manifest.manifest import (
    FolderRule,
    Manifest,
)
from .global_config import (
    _GlobalConfig,
)

CONFIG = _GlobalConfig()
# isort: on

from .app import (
    App,
    BuildStatus,
    CMakeApp,
)
from .log import (
    setup_logging,
)
from .main import (
    build_apps,
    find_apps,
)

__all__ = [
    'App',
    'BuildStatus',
    'CMakeApp',
    'CONFIG',
    'FolderRule',
    'LOGGER',
    'Manifest',
    'build_apps',
    'find_apps',
    'setup_logging',
]
