# SPDX-FileCopyrightText: 2022-2023 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

"""
Tools for building ESP-IDF related apps.
"""

import logging

__version__ = '0.6.0'

LOGGER = logging.getLogger('idf_build_apps')

from .app import (
    App,
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
    'CMakeApp',
    'find_apps',
    'build_apps',
    'setup_logging',
]
