# SPDX-FileCopyrightText: 2026 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import logging
import typing as t

from .app import App
from .utils import InvalidCommand
from .utils import get_parallel_start_stop

LOGGER = logging.getLogger(__name__)


class AppScheduler:
    def iter_apps(self, apps: t.List[App]) -> t.Iterator[t.Tuple[int, App]]:
        raise NotImplementedError

    def mark_running(self, index: int, app: App) -> None:
        pass

    def mark_success(self, index: int, app: App) -> None:
        pass

    def mark_failed(self, index: int, app: App) -> None:
        pass


class SliceScheduler(AppScheduler):
    def __init__(self, parallel_count: int = 1, parallel_index: int = 1) -> None:
        self.parallel_count = parallel_count
        self.parallel_index = parallel_index

    def iter_apps(self, apps: t.List[App]) -> t.Iterator[t.Tuple[int, App]]:
        start, stop = get_parallel_start_stop(len(apps), self.parallel_count, self.parallel_index)
        LOGGER.info('Processing %d total apps: building apps %d-%d', len(apps), start, stop)

        for i, app in enumerate(apps):
            index = i + 1  # we use 1-based
            if index < start or index > stop:
                continue

            yield index, app


class RedisPullScheduler(AppScheduler):
    STATUS_RUNNING = 'running'
    STATUS_SUCCESS = 'success'
    STATUS_FAILED = 'failed'

    def __init__(self, redis_url: str, queue_key: str, *, status_key: t.Optional[str] = None) -> None:
        try:
            import redis
        except ImportError as e:
            raise InvalidCommand('Redis pull mode requires the "redis" Python package to be installed.') from e

        self.redis_client = redis.Redis.from_url(redis_url)
        self.queue_key = queue_key
        self.status_key = status_key

    def iter_apps(self, apps: t.List[App]) -> t.Iterator[t.Tuple[int, App]]:
        LOGGER.info('Processing %d total apps in Redis pull mode from queue %s', len(apps), self.queue_key)

        while True:
            app_id = self.redis_client.incr(self.queue_key) - 1
            if app_id >= len(apps):
                LOGGER.info('No more apps to build')
                return
            if app_id < 0:
                raise InvalidCommand(f'Redis queue {self.queue_key} returned invalid app id {app_id}.')

            index = app_id + 1
            yield index, apps[app_id]

    def _set_status(self, index: int, status: str) -> None:
        if self.status_key:
            self.redis_client.hset(self.status_key, index - 1, status)

    def mark_running(self, index: int, app: App) -> None:  # noqa: ARG002
        self._set_status(index, self.STATUS_RUNNING)

    def mark_success(self, index: int, app: App) -> None:  # noqa: ARG002
        self._set_status(index, self.STATUS_SUCCESS)

    def mark_failed(self, index: int, app: App) -> None:  # noqa: ARG002
        self._set_status(index, self.STATUS_FAILED)
