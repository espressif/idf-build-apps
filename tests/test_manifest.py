# SPDX-FileCopyrightText: 2022-2023 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import os

from packaging.version import (
    Version,
)

import idf_build_apps.constants
from idf_build_apps.manifest.if_parser import (
    BOOL_STMT,
)
from idf_build_apps.manifest.manifest import (
    Manifest,
)


def test_manifest(tmpdir):
    yaml_file = tmpdir / 'test.yml'
    yaml_file.write_text(
        """
test1:
    enable:
        - if: IDF_TARGET == "esp32" or IDF_TARGET == "esp32c3"
        - if: IDF_TARGET == "esp32s2" and IDF_VERSION_MAJOR in [4, 5]
    disable_test:
        - if: IDF_TARGET == "esp32c3"

test2:
    enable:
        - if: INCLUDE_DEFAULT == 0 and IDF_TARGET == "linux"
""",
        encoding='utf8',
    )

    os.chdir(tmpdir)
    Manifest.ROOTPATH = tmpdir
    manifest = Manifest.from_file(yaml_file)

    assert manifest.enable_build_targets('test1') == ['esp32', 'esp32c3', 'esp32s2']
    assert manifest.enable_test_targets('test1') == ['esp32', 'esp32s2']
    assert manifest.enable_build_targets('test2') == ['linux']
    assert manifest.enable_test_targets('test2') == ['linux']


class TestIfParser:
    def test_idf_version(self, monkeypatch):
        monkeypatch.setattr(idf_build_apps.manifest.if_parser, 'IDF_VERSION', Version('5.9.0'))
        statement = 'IDF_VERSION > "5.10.0"'
        assert BOOL_STMT.parseString(statement)[0].get_value('esp32', 'foo') is False

        statement = 'IDF_VERSION in  ["5.9.0"]'
        assert BOOL_STMT.parseString(statement)[0].get_value('esp32', 'foo') is True
