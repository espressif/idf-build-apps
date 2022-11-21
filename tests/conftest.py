# SPDX-FileCopyrightText: 2022 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import pytest

from idf_build_apps import App


@pytest.fixture(autouse=True)
def clean_cls_attr():
    App.MANIFEST = None
