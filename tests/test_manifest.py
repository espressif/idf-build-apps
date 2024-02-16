# SPDX-FileCopyrightText: 2022-2024 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import os
import shutil

import pytest
import yaml
from packaging.version import (
    Version,
)

import idf_build_apps
from idf_build_apps.constants import (
    SUPPORTED_TARGETS,
)
from idf_build_apps.manifest.if_parser import (
    BOOL_STMT,
)
from idf_build_apps.manifest.manifest import (
    Manifest,
)
from idf_build_apps.utils import (
    InvalidManifest,
)
from idf_build_apps.yaml import (
    parse,
)


def test_manifest(tmpdir, recwarn, monkeypatch):
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

    monkeypatch.setattr(idf_build_apps.manifest.manifest.Manifest, 'CHECK_MANIFEST_RULES', True)
    with pytest.raises(InvalidManifest, match=msg_fmt.format(os.path.join(tmpdir, 'test1'), yaml_file)):
        Manifest.from_file(yaml_file)

    # test with folder that has the same prefix as one of the folders in the manifest
    assert manifest.enable_build_targets('test23') == sorted(SUPPORTED_TARGETS)


def test_manifest_switch_clause(tmpdir):
    yaml_file = tmpdir / 'test.yml'
    from idf_build_apps.constants import (
        IDF_VERSION,
    )

    yaml_file.write_text(
        f"""
test1:
  depends_components:
    - if: IDF_VERSION == "{IDF_VERSION}"
      content: [ "VVV" ]
    - if: CONFIG_NAME == "AAA"
      content: [ "AAA" ]
    - default: ["some_1", "some_2", "some_3"]

test2:
  depends_components:
    - if: IDF_TARGET == "esp32"
      content: [ "esp32" ]
    - if: CONFIG_NAME == "AAA"
      content: [ "AAA" ]
    - if: IDF_VERSION == "{IDF_VERSION}"
      content: [ "VVV" ]
    - default: ["some_1", "some_2", "some_3"]

test3:
  depends_components:
    - if: CONFIG_NAME == "AAA"
      content: [ "AAA" ]
    - if: CONFIG_NAME == "BBB"
      content: [ "BBB" ]
    - default: ["some_1", "some_2", "some_3"]

test4:
  depends_components:
    - if: CONFIG_NAME == "BBB"
      content: [ "BBB" ]
    - if: CONFIG_NAME == "AAA"
      content: [ "AAA" ]

test5:
  depends_components:
    - "some_1"
    - "some_2"
    - "some_3"

""",
        encoding='utf8',
    )

    os.chdir(tmpdir)
    Manifest.ROOTPATH = tmpdir
    manifest = Manifest.from_file(yaml_file)

    assert manifest.depends_components('test1', None, None) == ['VVV']
    assert manifest.depends_components('test1', None, 'AAA') == ['VVV']

    assert manifest.depends_components('test2', 'esp32', None) == ['esp32']
    assert manifest.depends_components('test2', None, 'AAA') == ['AAA']
    assert manifest.depends_components('test2', 'esp32', 'AAA') == ['esp32']
    assert manifest.depends_components('test2', None, None) == ['VVV']

    assert manifest.depends_components('test3', 'esp32', 'AAA') == ['AAA']
    assert manifest.depends_components('test3', 'esp32', 'BBB') == ['BBB']
    assert manifest.depends_components('test3', 'esp32', '123123') == ['some_1', 'some_2', 'some_3']
    assert manifest.depends_components('test3', None, None) == ['some_1', 'some_2', 'some_3']

    assert manifest.depends_components('test4', 'esp32', 'AAA') == ['AAA']
    assert manifest.depends_components('test4', 'esp32', 'BBB') == ['BBB']
    assert manifest.depends_components('test4', 'esp32', '123123') == []
    assert manifest.depends_components('test4', None, None) == []

    assert manifest.depends_components('test5', 'esp32', 'AAA') == ['some_1', 'some_2', 'some_3']
    assert manifest.depends_components('test5', 'esp32', 'BBB') == ['some_1', 'some_2', 'some_3']
    assert manifest.depends_components('test5', 'esp32', '123123') == ['some_1', 'some_2', 'some_3']
    assert manifest.depends_components('test5', None, None) == ['some_1', 'some_2', 'some_3']


def test_manifest_switch_clause_with_postfix(tmpdir):
    yaml_file = tmpdir / 'test.yml'

    yaml_file.write_text(
        """
.test: &test
  depends_components+:
    - if: CONFIG_NAME == "AAA"
      content: ["NEW_AAA"]
    - if: CONFIG_NAME == "BBB"
      content: ["NEW_BBB"]
  depends_components-:
    - if: CONFIG_NAME == "CCC"

test1:
  <<: *test
  depends_components:
    - if: CONFIG_NAME == "AAA"
      content: [ "AAA" ]
    - if: CONFIG_NAME == "CCC"
      content: [ "CCC" ]
    - default: ["DF"]
""",
        encoding='utf8',
    )
    os.chdir(tmpdir)
    Manifest.ROOTPATH = tmpdir
    manifest = Manifest.from_file(yaml_file)

    assert manifest.depends_components('test1', None, None) == ['DF']
    assert manifest.depends_components('test1', None, 'CCC') == ['DF']
    assert manifest.depends_components('test1', None, 'AAA') == ['NEW_AAA']
    assert manifest.depends_components('test1', None, 'BBB') == ['NEW_BBB']


def test_manifest_switch_clause_wrong_manifest_format(tmpdir):
    yaml_file = tmpdir / 'test.yml'
    from idf_build_apps.constants import (
        IDF_VERSION,
    )

    yaml_file.write_text(
        f"""
    test1:
      depends_components:
        - if: IDF_VERSION == "{IDF_VERSION}"
          content: [ "VVV" ]
        - default: ["some_1", "some_2", "some_3"]
        - hello: 123

    """,
        encoding='utf8',
    )
    try:
        Manifest.from_file(yaml_file)
    except InvalidManifest as e:
        assert str(e) == "Only the 'if' and 'default' keywords are supported in switch clause."

    yaml_file.write_text(
        f"""
        test1:
          depends_components:
            - if: IDF_VERSION == "{IDF_VERSION}"
              content: [ "VVV" ]
            - default: ["some_1", "some_2", "some_3"]
            - 123
            - 234
        """,
        encoding='utf8',
    )
    try:
        Manifest.from_file(yaml_file)
    except InvalidManifest as e:
        assert str(e) == 'Current manifest format has to fit either the switch format or the list format.'


def test_manifest_with_anchor(tmpdir, monkeypatch):
    yaml_file = tmpdir / 'test.yml'
    yaml_file.write_text(
        """
.base: &base
  depends_components:
    - a

foo: &foo
  <<: *base
  disable:
    - if: IDF_TARGET == "esp32"

bar:
  <<: *foo
""",
        encoding='utf8',
    )

    monkeypatch.setattr(idf_build_apps.manifest.manifest.FolderRule, 'DEFAULT_BUILD_TARGETS', ['esp32'])

    with pytest.warns(UserWarning, match='Folder ".+" does not exist. Please check your manifest file'):
        manifest = Manifest.from_file(yaml_file)

    assert manifest.enable_build_targets('bar') == []


def test_manifest_with_anchor_and_postfix(tmpdir):
    yaml_file = tmpdir / 'test.yml'

    yaml_file.write_text(
        """
foo:
""",
        encoding='utf8',
    )
    manifest = Manifest.from_file(yaml_file)
    assert manifest.enable_build_targets('foo') == sorted(SUPPORTED_TARGETS)

    yaml_file.write_text(
        """
.base_depends_components: &base-depends-components
  depends_components:
    - esp_hw_support
    - esp_rom
    - esp_wifi

examples/wifi/coexist:
  <<: *base-depends-components
  depends_components+:
    - esp_coex
  depends_components-:
    - esp_rom
""",
        encoding='utf8',
    )

    manifest = Manifest.from_file(yaml_file)
    assert manifest.depends_components('examples/wifi/coexist') == ['esp_coex', 'esp_hw_support', 'esp_wifi']

    yaml_file.write_text(
        """
.base: &base
  enable:
    - if: IDF_VERSION == "5.2.0"
    - if: IDF_VERSION == "5.3.0"

foo:
  <<: *base
  enable+:
    - if: IDF_VERSION == "5.2.0"
      temp: true
    - if: IDF_VERSION == "5.4.0"
      reason: bar
""",
        encoding='utf8',
    )
    s_manifest_dict = parse(yaml_file)

    yaml_file.write_text(
        """
foo:
    enable:
        -   if: IDF_VERSION == "5.3.0"
        -   if: IDF_VERSION == "5.2.0"
            temp: true
        -   if: IDF_VERSION == "5.4.0"
            reason: bar
""",
        encoding='utf8',
    )
    with open(yaml_file) as f:
        manifest_dict = yaml.safe_load(f) or {}

    assert s_manifest_dict['foo'] == manifest_dict['foo']

    yaml_file.write_text(
        """
.base: &base
  enable:
    - if: IDF_VERSION == "5.3.0"

foo:
  <<: *base
  enable+:
    - if: IDF_VERSION == "5.2.0"
      temp: true
    - if: IDF_VERSION == "5.4.0"
      reason: bar
""",
        encoding='utf8',
    )

    s_manifest_dict = parse(yaml_file)

    yaml_file.write_text(
        """
foo:
    enable:
        -   if: IDF_VERSION == "5.3.0"
        -   if: IDF_VERSION == "5.2.0"
            temp: true
        -   if: IDF_VERSION == "5.4.0"
            reason: bar
""",
        encoding='utf8',
    )
    with open(yaml_file) as f:
        manifest_dict = yaml.safe_load(f) or {}

    assert s_manifest_dict['foo'] == manifest_dict['foo']

    yaml_file.write_text(
        """
.test: &test
  depends_components:
    - a
    - b

foo:
  <<: *test
  depends_components+:
    - c

bar:
  <<: *test
  depends_components+:
    - d
""",
        encoding='utf8',
    )
    s_manifest_dict = parse(yaml_file)
    foo = s_manifest_dict['foo']
    bar = s_manifest_dict['bar']
    assert foo['depends_components'] == ['a', 'b', 'c']
    assert bar['depends_components'] == ['a', 'b', 'd']
    assert id(foo['depends_components']) != id(bar['depends_components'])

    yaml_file.write_text(
        """
.test: &test
  depends_components:
    - if: 1
      value: 123

foo:
  <<: *test
  depends_components+:
    - if: 2
      value: 234

bar:
  <<: *test
  depends_components+:
    - if: 2
      value: 345
""",
        encoding='utf8',
    )
    s_manifest_dict = parse(yaml_file)
    foo = s_manifest_dict['foo']
    bar = s_manifest_dict['bar']
    assert id(foo['depends_components']) != id(bar['depends_components'])
    print(s_manifest_dict)


def test_manifest_postfix_order(tmpdir):
    yaml_file = tmpdir / 'test.yml'
    yaml_file.write_text(
        """
.base_depends_components: &base-depends-components
  depends_components:
    - esp_hw_support

examples/wifi/coexist:
  <<: *base-depends-components
  depends_components+:
    - esp_coex
  depends_components-:
    - esp_coex
""",
        encoding='utf8',
    )

    manifest = Manifest.from_file(yaml_file)
    assert manifest.depends_components('examples/wifi/coexist') == ['esp_hw_support']


def test_from_files_duplicates(tmp_path, monkeypatch):
    yaml_file_1 = tmp_path / 'test1.yml'
    yaml_file_1.write_text(
        """
foo:
  enable:
    - if: IDF_TARGET == "esp32"
""",
        encoding='utf8',
    )

    yaml_file_2 = tmp_path / 'test2.yml'
    yaml_file_2.write_text(
        """
foo:
    enable:
        - if: IDF_TARGET == "esp32"
""",
        encoding='utf8',
    )

    monkeypatch.setattr(idf_build_apps.manifest.manifest.Manifest, 'CHECK_MANIFEST_RULES', True)
    folder_path = os.path.join(os.getcwd(), 'foo')
    os.makedirs(folder_path)

    with pytest.raises(InvalidManifest, match=f'Folder "{folder_path}" is already defined in {yaml_file_1!s}'):
        Manifest.from_files([str(yaml_file_1), str(yaml_file_2)])

    monkeypatch.setattr(idf_build_apps.manifest.manifest.Manifest, 'CHECK_MANIFEST_RULES', False)
    with pytest.warns(UserWarning, match=f'Folder "{folder_path}" is already defined in {yaml_file_1!s}'):
        Manifest.from_files([str(yaml_file_1), str(yaml_file_2)])


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
