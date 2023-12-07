# SPDX-FileCopyrightText: 2023 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import typing as t

from pydantic import (
    computed_field,
)

from .utils import (
    BaseModel,
)


class BuildAppsArgs(BaseModel):
    PARALLEL_INDEX_PLACEHOLDER: t.ClassVar[str] = '@p'  # replace it with the parallel index

    parallel_index: int = 1
    parallel_count: int = 1

    _junitxml: t.Optional[str] = None
    _collect_app_info: t.Optional[str] = None
    _collect_size_info: t.Optional[str] = None

    def __init__(
        self,
        *,
        collect_app_info: t.Optional[str] = None,
        collect_size_info: t.Optional[str] = None,
        junitxml: t.Optional[str] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)

        self._junitxml = junitxml
        self._collect_app_info = collect_app_info
        self._collect_size_info = collect_size_info

    @computed_field  # type: ignore
    @property
    def collect_app_info(self) -> t.Optional[str]:
        if self._collect_app_info:
            return self.expand(self._collect_app_info)

        return None

    @computed_field  # type: ignore
    @property
    def collect_size_info(self) -> t.Optional[str]:
        if self._collect_size_info:
            return self.expand(self._collect_size_info)

        return None

    @computed_field  # type: ignore
    @property
    def junitxml(self) -> t.Optional[str]:
        if self._junitxml:
            return self.expand(self._junitxml)

        return None

    def expand(self, path):
        return path.replace(self.PARALLEL_INDEX_PLACEHOLDER, str(self.parallel_index))
