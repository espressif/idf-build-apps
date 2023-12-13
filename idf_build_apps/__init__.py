# SPDX-FileCopyrightText: 2022-2023 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

"""
Tools for building ESP-IDF related apps.
"""

# ruff: noqa: E402
# avoid circular imports

__version__ = '2.0.0b5'

from .session_args import (
    SessionArgs,
)

SESSION_ARGS = SessionArgs()

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
    'SESSION_ARGS',
]
