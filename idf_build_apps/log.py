# SPDX-FileCopyrightText: 2023-2024 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import logging
import sys
import typing as t

from .constants import (
    BuildStage,
)


class ColoredFormatter(logging.Formatter):
    grey: str = '\x1b[37;20m'
    yellow: str = '\x1b[33;20m'
    red: str = '\x1b[31;20m'
    bold_red: str = '\x1b[31;1m'

    reset: str = '\x1b[0m'

    fmt: str = '%(asctime)s %(levelname)8s %(message)s'
    app_fmt: str = f'%(asctime)s %(levelname)8s [%(build_stage){BuildStage.max_length()}s] %(message)s'

    datefmt: str = '%Y-%m-%d %H:%M:%S'

    FORMATS: t.Dict[int, str] = {
        logging.DEBUG: f'{grey}{{}}{reset}',
        logging.INFO: '{}',
        logging.WARNING: f'{yellow}{{}}{reset}',
        logging.ERROR: f'{red}{{}}{reset}',
        logging.CRITICAL: f'{bold_red}{{}}{reset}',
    }

    def __init__(self, colored: bool = True) -> None:
        self.colored = colored
        if sys.platform == 'win32':  # does not support it
            self.colored = False

        super().__init__(datefmt=self.datefmt)

    def format(self, record: logging.LogRecord) -> str:
        if getattr(record, 'build_stage', None):
            base_fmt = self.app_fmt
        else:
            base_fmt = self.fmt

        if self.colored:
            log_fmt = self.FORMATS[record.levelno].format(base_fmt)
        else:
            log_fmt = base_fmt

        if record.levelno in [logging.WARNING, logging.ERROR]:
            record.msg = '>>> ' + str(record.msg)
        elif record.levelno == logging.CRITICAL:
            record.msg = '!!! ' + str(record.msg)

        formatter = logging.Formatter(log_fmt, datefmt=self.datefmt)
        return formatter.format(record)


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

    package_logger = logging.getLogger(__package__)
    package_logger.setLevel(level)
    if log_file:
        handler: logging.Handler = logging.FileHandler(log_file)
    else:
        handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(ColoredFormatter(colored))

    if package_logger.hasHandlers():
        package_logger.handlers.clear()
    package_logger.addHandler(handler)
    package_logger.propagate = False  # don't propagate to root logger
