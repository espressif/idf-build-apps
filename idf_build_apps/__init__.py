# SPDX-FileCopyrightText: 2022-2026 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

"""
Tools for building ESP-IDF related apps.
"""

# ruff: noqa: E402
# avoid circular imports

__version__ = '2.16.0'

from .session_args import SessionArgs

SESSION_ARGS = SessionArgs()

from .app import App
from .app import AppDeserializer
from .app import CMakeApp
from .app import MakeApp
from .log import setup_logging
from .main import build_apps
from .main import find_apps
from .main import json_list_files_to_apps
from .main import json_to_app

__all__ = [
    'App',
    'AppDeserializer',
    'CMakeApp',
    'MakeApp',
    'build_apps',
    'find_apps',
    'json_list_files_to_apps',
    'json_to_app',
    'setup_logging',
]
