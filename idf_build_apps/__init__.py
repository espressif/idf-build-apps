# SPDX-FileCopyrightText: 2022-2023 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

"""
Tools for building ESP-IDF related apps.
"""

# ruff: noqa: E402
# avoid circular imports

import logging

__version__ = '2.0.0b4'

LOGGER = logging.getLogger('idf_build_apps')

from .app import (
    App,
    AppDeserializer,
    CMakeApp,
    MakeApp,
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
    'AppDeserializer',
    'CMakeApp',
    'MakeApp',
    'find_apps',
    'build_apps',
    'setup_logging',
]
