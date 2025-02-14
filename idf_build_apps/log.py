# SPDX-FileCopyrightText: 2023-2025 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import logging
import os
import sys
import typing as t

from rich import get_console
from rich.logging import RichHandler


def setup_logging(verbose: int = 0, log_file: t.Optional[str] = None, colored: bool = True) -> None:
    """
    Setup logging stream handler

    :param verbose: 0 - WARNING, 1 - INFO, 2 - DEBUG
    :param log_file: log file path
    :param colored: colored output or not
    :return: None
    """
    if not verbose:
        level = logging.WARNING
    elif verbose == 1:
        level = logging.INFO
    else:
        level = logging.DEBUG

    console = get_console()
    console.no_color = not colored
    console.stderr = True
    # no line break while testing
    if os.getenv('__IS_TESTING'):
        console.width = sys.maxsize

    package_logger = logging.getLogger(__package__)
    package_logger.setLevel(level)
    if log_file:
        handler: logging.Handler = logging.FileHandler(log_file)
    else:
        handler = RichHandler(
            level,
            console,
            show_path=False,
            omit_repeated_times=False,
        )

    if package_logger.hasHandlers():
        package_logger.handlers.clear()
    package_logger.addHandler(handler)
    package_logger.propagate = False  # don't propagate to root logger
