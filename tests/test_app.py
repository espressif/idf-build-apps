# SPDX-FileCopyrightText: 2023 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

from idf_build_apps import (
    CMakeApp,
)


def test_serialization():
    a = CMakeApp('foo', 'bar')
    a_s = a.to_json()

    b = CMakeApp.model_validate_json(a_s)
    assert a == b
