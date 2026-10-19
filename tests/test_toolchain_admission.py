# SPDX-FileCopyrightText: 2026 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0
import pytest
from conftest import create_project

from idf_build_apps.app import App
from idf_build_apps.app import CMakeApp
from idf_build_apps.constants import BuildStatus
from idf_build_apps.main import find_apps
from idf_build_apps.manifest.manifest import Manifest
from idf_build_apps.utils import InvalidManifest


@pytest.mark.parametrize('value', ['null', 'gcc', '""', '[gcc, ""]', '[gcc, null]', '[1]', '{}'])
def test_invalid_supported_toolchains(tmp_path, value):
    (tmp_path / 'app').mkdir()
    manifest_file = tmp_path / 'manifest.yml'
    manifest_file.write_text(f'app:\n  supported_toolchains: {value}\n')
    with pytest.raises(InvalidManifest, match='supported_toolchains'):
        Manifest.from_file(manifest_file, root_path=tmp_path)


def test_nearest_rule_does_not_inherit_toolchains(tmp_path, monkeypatch):
    (tmp_path / 'parent' / 'child').mkdir(parents=True)
    manifest_file = tmp_path / 'manifest.yml'
    manifest_file.write_text('parent:\n  supported_toolchains: [clang]\nparent/child:\n  disable_test: []\n')
    manifest = Manifest.from_file(manifest_file, root_path=tmp_path)

    monkeypatch.setenv('IDF_TOOLCHAIN', 'clang')
    assert 'esp32' in manifest.enable_build_targets(str(tmp_path / 'parent'))
    assert manifest.enable_build_targets(str(tmp_path / 'parent/child')) == []
    assert manifest.enable_build_targets(str(tmp_path / 'unmatched')) == []

    monkeypatch.setenv('IDF_TOOLCHAIN', 'gcc')
    assert manifest.enable_build_targets(str(tmp_path / 'parent')) == []
    assert 'esp32' in manifest.enable_build_targets(str(tmp_path / 'parent/child'))
    assert 'esp32' in manifest.enable_build_targets(str(tmp_path / 'unmatched'))


def test_toolchain_rules_and_test_only_disable(tmp_path, monkeypatch):
    create_project('app', tmp_path)
    manifest_file = tmp_path / 'manifest.yml'
    manifest_file.write_text("""app:
  supported_toolchains: [gcc, clang]
  enable:
    - if: IDF_TARGET == "esp32"
  disable:
    - if: IDF_TOOLCHAIN == "clang" and CONFIG_NAME != "clang"
    - if: IDF_TOOLCHAIN != "clang" and CONFIG_NAME != "default"
  disable_test:
    - if: IDF_TOOLCHAIN == "clang"
  depends_components: [freertos, xtensa]
""")
    for toolchain, config, disabled, test_disabled in [
        ('gcc', 'default', False, False),
        ('gcc', 'clang', True, True),
        ('clang', 'clang', False, True),
        ('clang', 'default', True, True),
    ]:
        monkeypatch.setenv('IDF_TOOLCHAIN', toolchain)
        App.MANIFEST = Manifest.from_file(manifest_file, root_path=tmp_path)
        app = CMakeApp(str(tmp_path / 'app'), 'esp32', config_name=config)
        app.check_should_build()
        app.check_should_test()
        assert (app.build_status == BuildStatus.DISABLED) is disabled
        assert (app.test_comment is not None) is test_disabled
        assert app.depends_components == ['freertos', 'xtensa']


@pytest.mark.parametrize(
    'declaration,toolchain,disabled',
    [
        ('', 'clang', True),
        ('  supported_toolchains: []\n', 'gcc', True),
        ('  supported_toolchains: [clang]\n', 'gcc', True),
        ('  supported_toolchains: [clang]\n', 'clang', False),
        ('  supported_toolchains: [gcc, clang]\n', 'clang', False),
        ('  supported_toolchains: [custom]\n', 'custom', False),
    ],
)
def test_declaration_is_sole_admission(tmp_path, monkeypatch, declaration, toolchain, disabled):
    monkeypatch.setenv('IDF_TOOLCHAIN', toolchain)
    create_project('app', tmp_path)
    manifest_file = tmp_path / 'manifest.yml'
    manifest_file.write_text('app:\n' + declaration + '  enable:\n    - if: IDF_TARGET == "esp32"\n')
    apps = find_apps(str(tmp_path / 'app'), 'esp32', manifest_files=[str(manifest_file)], include_disabled_apps=True)
    assert len(apps) == 1
    assert (apps[0].build_status == BuildStatus.DISABLED) is disabled
    if disabled:
        assert apps[0].build_comment and 'Toolchain' in apps[0].build_comment
        assert apps[0].test_comment and 'Toolchain' in apps[0].test_comment


def test_no_manifest_defaults_to_gcc_only(tmp_path, monkeypatch):
    create_project('app', tmp_path)
    monkeypatch.setenv('IDF_TOOLCHAIN', 'clang')
    apps = find_apps(str(tmp_path / 'app'), 'esp32', include_disabled_apps=True)
    assert len(apps) == 1
    assert apps[0].build_status == BuildStatus.DISABLED
    assert apps[0].supported_targets == []
    assert apps[0].build_comment and 'Toolchain clang' in apps[0].build_comment
    assert apps[0].test_comment and 'Toolchain clang' in apps[0].test_comment


def test_toolchain_expression_does_not_grant_admission(tmp_path, monkeypatch):
    create_project('app', tmp_path)
    manifest_file = tmp_path / 'manifest.yml'
    manifest_file.write_text('app:\n  enable:\n    - if: IDF_TOOLCHAIN == "clang"\n')
    monkeypatch.setenv('IDF_TOOLCHAIN', 'clang')
    apps = find_apps(str(tmp_path / 'app'), 'esp32', manifest_files=[str(manifest_file)], include_disabled_apps=True)
    assert len(apps) == 1
    assert apps[0].build_status == BuildStatus.DISABLED
    assert apps[0].build_comment and 'Toolchain clang' in apps[0].build_comment


def test_unset_toolchain_uses_gcc_default(tmp_path, monkeypatch):
    monkeypatch.delenv('IDF_TOOLCHAIN', raising=False)
    create_project('app', tmp_path)
    assert len(find_apps(str(tmp_path / 'app'), 'esp32')) == 1


def test_toolchain_change_updates_sha(tmp_path):
    (tmp_path / 'app').mkdir()
    manifest_file = tmp_path / 'manifest.yml'
    manifest_file.write_text('app:\n  supported_toolchains: [gcc]\n')
    gcc_sha = Manifest.from_file(manifest_file, root_path=tmp_path).rules[0].sha
    manifest_file.write_text('app:\n  supported_toolchains: [gcc, clang]\n')
    assert Manifest.from_file(manifest_file, root_path=tmp_path).rules[0].sha != gcc_sha
