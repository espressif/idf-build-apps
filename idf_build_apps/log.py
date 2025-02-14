# SPDX-FileCopyrightText: 2023-2025 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import logging
import typing as t
from datetime import datetime

from rich import get_console
from rich._log_render import LogRender
from rich.console import Console, ConsoleRenderable
from rich.containers import Renderables
from rich.logging import RichHandler
from rich.text import Text, TextType


class _OneLineLogRender(LogRender):
    def __call__(  # type: ignore # the original method returns Table instead of Text
        self,
        console: Console,
        renderables: t.Iterable[ConsoleRenderable],
        log_time: t.Optional[datetime] = None,
        time_format: t.Optional[t.Union[str, t.Callable[[datetime], Text]]] = None,
        level: TextType = '',
        path: t.Optional[str] = None,
        line_no: t.Optional[int] = None,
        link_path: t.Optional[str] = None,
    ) -> Text:
        output = Text(no_wrap=True)
        if self.show_time:
            log_time = log_time or console.get_datetime()
            time_format = time_format or self.time_format
            if callable(time_format):
                log_time_display = time_format(log_time)
            else:
                log_time_display = Text(log_time.strftime(time_format), style='log.time')
            if log_time_display == self._last_time and self.omit_repeated_times:
                output.append(' ' * len(log_time_display), style='log.time')
            else:
                output.append(log_time_display)
                self._last_time = log_time_display
            output.pad_right(1)

        if self.show_level:
            output.append(level)
            if self.level_width:
                output.pad_right(max(1, self.level_width - len(level)))
            else:
                output.pad_right(1)

        for renderable in Renderables(renderables):  # type: ignore
            if isinstance(renderable, Text):
                renderable.stylize('log.message')

            output.append(renderable)
            output.pad_right(1)

        if self.show_path and path:
            path_text = Text(style='log.path')
            path_text.append(path, style=f'link file://{link_path}' if link_path else '')
            if line_no:
                path_text.append(':')
                path_text.append(
                    f'{line_no}',
                    style=f'link file://{link_path}#{line_no}' if link_path else '',
                )
            output.append(path_text)
            output.pad_right(1)

        output.rstrip()
        return output


def get_rich_log_handler(level: int = logging.WARNING, no_color: bool = False) -> RichHandler:
    console = get_console()
    console.soft_wrap = True
    console.no_color = no_color
    console.stderr = True

    handler = RichHandler(
        level,
        console,
    )
    handler._log_render = _OneLineLogRender(
        show_level=True,
        show_path=False,
        omit_repeated_times=False,
    )

    return handler


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
        handler = get_rich_log_handler(level, not colored)
    if package_logger.hasHandlers():
        package_logger.handlers.clear()
    package_logger.addHandler(handler)

    package_logger.propagate = False  # don't propagate to root logger
