# SPDX-FileCopyrightText: 2023-2025 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0
import contextlib
import os

import pytest
from pydantic import (
    ValidationError,
)

from idf_build_apps import (
    AppDeserializer,
    CMakeApp,
    MakeApp,
)
from idf_build_apps.main import (
    json_to_app,
)
from idf_build_apps.utils import Literal


def test_serialization():
    a = CMakeApp('foo', 'bar')
    a_s = a.to_json()

    b = CMakeApp.model_validate_json(a_s)
    assert a == b


def test_deserialization():
    a = CMakeApp('foo', 'bar', size_json_filename='size.json')
    b = MakeApp('foo', 'bar', build_log_filename='build.log')

    assert a != b

    with open('test.txt', 'w') as fw:
        fw.write(a.to_json() + '\n')
        fw.write(b.to_json() + '\n')

    with open('test.txt') as fr:
        a_s = AppDeserializer.from_json(fr.readline())
        b_s = AppDeserializer.from_json(fr.readline())

    assert a == a_s
    assert b == b_s


def test_app_sorting():
    a = CMakeApp('foo', 'esp32')
    b = MakeApp('foo', 'esp32')

    c = CMakeApp('foo', 'esp32', size_json_filename='size.json')
    d = CMakeApp('foo', 'esp32s2')
    e = CMakeApp('foo', 'esp32s2', build_comment='build_comment')

    with pytest.raises(TypeError, match="'<' not supported between instances of 'CMakeApp' and 'MakeApp'"):
        assert a < b

    assert a < c < d
    assert d > c > a

    # __EQ_IGNORE_FIELDS__
    assert d == e
    assert not d < e
    assert not d > e


def test_app_deserializer():
    a = CMakeApp('foo', 'esp32')
    b = MakeApp('foo', 'esp32')

    class CustomApp(CMakeApp):
        build_system: Literal['custom'] = 'custom'  # type: ignore

    c = CustomApp('foo', 'esp32')

    assert json_to_app(a.to_json()) == a
    assert json_to_app(b.to_json()) == b

    with pytest.raises(
        ValidationError,
        match="Input tag 'custom' found using 'build_system' does not match any of the expected tags: 'cmake', 'make'",
    ):
        assert json_to_app(c.to_json()) == c

    assert json_to_app(c.to_json(), extra_classes=[CustomApp]) == c


def test_app_init_from_another():
    a = CMakeApp('foo', 'esp32', build_dir='build_@t_')
    b = CMakeApp.from_another(a, target='esp32c3')

    assert isinstance(b, CMakeApp)
    assert a.target == 'esp32'
    assert b.target == 'esp32c3'
    assert 'build_esp32_' == a.build_dir
    assert 'build_esp32c3_' == b.build_dir


def test_app_hash():
    a = CMakeApp('foo', 'esp32')
    b = CMakeApp('foo/', 'esp32')
    assert a == b
    assert hash(a) == hash(b)
    assert len(list({a, b})) == 1

    with contextlib.chdir(os.path.expanduser('~')):
        a = CMakeApp('foo', 'esp32')
        b = CMakeApp(os.path.join('~', 'foo'), 'esp32')
        assert a == b
        assert hash(a) == hash(b)
        assert len(list({a, b})) == 1
