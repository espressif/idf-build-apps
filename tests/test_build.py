# SPDX-FileCopyrightText: 2022 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

from idf_build_apps.app import CMakeApp
from idf_build_apps.constants import IDF_PATH


def test_build(tmpdir):
    path = IDF_PATH / 'examples' / 'get-started' / 'hello_world'

    CMakeApp(str(path), 'esp32', work_dir=str(tmpdir / 'test')).build()
