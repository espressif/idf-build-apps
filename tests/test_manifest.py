# SPDX-FileCopyrightText: 2022-2023 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import os
import shutil

import pytest
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
from idf_build_apps.utils import (
    InvalidManifest,
)


def test_manifest(tmpdir, recwarn):
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
    msg_fmt = 'Folder "{}" does not exist. Please check your manifest file {}'

    # two warnings warn test1 test2 not exists
    assert len(recwarn) == 2
    assert recwarn.pop(UserWarning).message.args[0] == msg_fmt.format(os.path.join(tmpdir, 'test1'), yaml_file)
    assert recwarn.pop(UserWarning).message.args[0] == msg_fmt.format(os.path.join(tmpdir, 'test2'), yaml_file)

    assert manifest.enable_build_targets('test1') == ['esp32', 'esp32c3', 'esp32s2']
    assert manifest.enable_test_targets('test1') == ['esp32', 'esp32s2']
    assert manifest.enable_build_targets('test2') == ['linux']
    assert manifest.enable_test_targets('test2') == ['linux']

    Manifest.CHECK_MANIFEST_RULES = True
    with pytest.raises(InvalidManifest, match=msg_fmt.format(os.path.join(tmpdir, 'test1'), yaml_file)):
        Manifest.from_file(yaml_file)


class TestIfParser:
    def test_idf_version(self, monkeypatch):
        monkeypatch.setattr(idf_build_apps.manifest.if_parser, 'IDF_VERSION', Version('5.9.0'))
        statement = 'IDF_VERSION > "5.10.0"'
        assert BOOL_STMT.parseString(statement)[0].get_value('esp32', 'foo') is False

        statement = 'IDF_VERSION in  ["5.9.0"]'
        assert BOOL_STMT.parseString(statement)[0].get_value('esp32', 'foo') is True


@pytest.mark.skipif(not shutil.which('idf.py'), reason='idf.py not found')
def test_idf_version_keywords_type():
    from idf_build_apps.constants import (
        IDF_VERSION_MAJOR,
        IDF_VERSION_MINOR,
        IDF_VERSION_PATCH,
    )

    assert isinstance(IDF_VERSION_MAJOR, int)
    assert isinstance(IDF_VERSION_MINOR, int)
    assert isinstance(IDF_VERSION_PATCH, int)
