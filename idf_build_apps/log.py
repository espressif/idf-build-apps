# SPDX-FileCopyrightText: 2023 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import logging
import sys


class ColoredFormatter(logging.Formatter):
    grey = '\x1b[37;20m'
    yellow = '\x1b[33;20m'
    red = '\x1b[31;20m'
    bold_red = '\x1b[31;1m'

    reset = '\x1b[0m'

    fmt = '%(asctime)s %(levelname)8s %(message)s'
    datefmt = '%Y-%m-%d %H:%M:%S'

    FORMATS = {
        logging.DEBUG: grey + fmt + reset,
        logging.INFO: fmt,
        logging.WARNING: yellow + fmt + reset,
        logging.ERROR: red + fmt + reset,
        logging.CRITICAL: bold_red + fmt + reset,
    }

    def __init__(self, colored=True):  # type: (bool) -> None
        self.colored = colored
        if sys.platform == 'win32':  # does not support it
            self.colored = False

        super(ColoredFormatter, self).__init__(datefmt=self.datefmt)

    def format(self, record):
        if self.colored:
            log_fmt = self.FORMATS.get(record.levelno)
        else:
            log_fmt = self.fmt

        if record.levelno in [logging.WARNING, logging.ERROR]:
            record.msg = '>>> ' + str(record.msg)
        elif record.levelno in [logging.CRITICAL]:
            record.msg = '!!! ' + str(record.msg)

        formatter = logging.Formatter(log_fmt, datefmt=self.datefmt)
        return formatter.format(record)
