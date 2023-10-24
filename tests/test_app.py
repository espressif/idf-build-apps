# SPDX-FileCopyrightText: 2023 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

from idf_build_apps import (
    AppDeserializer,
    CMakeApp,
    MakeApp,
)


def test_serialization():
    a = CMakeApp('foo', 'bar')
    a_s = a.to_json()

    b = CMakeApp.model_validate_json(a_s)
    assert a == b


def test_deserialization(tmp_path):
    a = CMakeApp('foo', 'bar', size_json_filename='size.json')
    b = MakeApp('foo', 'bar', build_log_filename='build.log')

    assert a != b

    with open(tmp_path / 'test.txt', 'w') as fw:
        fw.write(a.to_json() + '\n')
        fw.write(b.to_json() + '\n')

    with open(tmp_path / 'test.txt') as fr:
        a_s = AppDeserializer.from_json(fr.readline())
        b_s = AppDeserializer.from_json(fr.readline())

    assert a == a_s
    assert b == b_s
