# SPDX-FileCopyrightText: 2022-2023 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import logging
import os
from pathlib import (
    Path,
)

import pytest
from conftest import (
    create_project,
)

from idf_build_apps.constants import (
    DEFAULT_SDKCONFIG,
    IDF_PATH,
)
from idf_build_apps.main import (
    find_apps,
)


class TestFindWithManifest:
    def test_manifest_rootpath_chdir(self):
        test_dir = IDF_PATH / 'examples' / 'get-started'

        yaml_file = test_dir / 'test.yml'
        yaml_file.write_text(
            '''
examples/get-started:
    enable:
        - if: IDF_TARGET != "esp32"
''',
            encoding='utf8',
        )

        os.chdir(IDF_PATH)
        assert not find_apps(str(test_dir), 'esp32', recursive=True, manifest_files=str(yaml_file))

        # manifest folder invalid
        os.chdir(test_dir)
        assert find_apps(str(test_dir), 'esp32', recursive=True, manifest_files=str(yaml_file))

    def test_manifest_rootpath_specified(self):
        test_dir = IDF_PATH / 'examples' / 'get-started'

        yaml_file = test_dir / 'test.yml'
        yaml_file.write_text(
            '''
get-started:
    enable:
        - if: IDF_TARGET != "esp32"
''',
            encoding='utf8',
        )

        assert find_apps(
            str(test_dir), 'esp32', recursive=True, manifest_files=str(yaml_file), manifest_rootpath=str(IDF_PATH)
        )

        assert not find_apps(
            str(test_dir),
            'esp32',
            recursive=True,
            manifest_files=str(yaml_file),
            manifest_rootpath=str(IDF_PATH / 'examples'),
        )

    def test_keyword_idf_target(self, tmpdir):
        test_dir = str(IDF_PATH / 'examples')
        apps = find_apps(test_dir, 'esp32', recursive=True)
        assert apps

        yaml_file = tmpdir / 'test.yml'
        yaml_file.write_text(
            f'''
{test_dir}:
    enable:
        - if: IDF_TARGET == "esp32s2"
''',
            encoding='utf8',
        )
        filtered_apps = find_apps(test_dir, 'esp32', recursive=True, manifest_files=yaml_file)
        assert not filtered_apps
        assert filtered_apps != apps

    def test_keyword_idf_version(self):
        test_dir = IDF_PATH / 'examples' / 'get-started'
        apps = find_apps(str(test_dir), 'esp32', recursive=True)
        assert apps

        yaml_file = test_dir / 'test.yml'
        yaml_file.write_text(
            '''
get-started:
    enable:
        - if: IDF_VERSION_MAJOR > 0 and IDF_VERSION_MINOR < 999 and IDF_VERSION_PATCH in [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
''',
            encoding='utf8',
        )
        assert find_apps(str(test_dir), 'esp32', recursive=True, manifest_files=str(yaml_file)) == apps

    @pytest.mark.parametrize(
        'depends_on_components, could_find_apps',
        [
            (None, True),
            ([], False),
            ('fake', False),
            ('soc', True),
            (['soc', 'fake'], True),
        ],
    )
    def test_with_requires_and_depends_on_components(self, tmpdir, depends_on_components, could_find_apps):
        test_dir = str(IDF_PATH / 'examples')
        apps = find_apps(test_dir, 'esp32', recursive=True)
        assert apps

        yaml_file = tmpdir / 'test.yml'
        yaml_file.write_text(
            f'''
{test_dir}:
    requires_components:
        - freertos
        - soc
''',
            encoding='utf8',
        )

        filtered_apps = find_apps(
            test_dir,
            'esp32',
            recursive=True,
            manifest_files=yaml_file,
            depends_on_components=depends_on_components,
        )
        if could_find_apps:
            assert filtered_apps == apps
        else:
            assert not filtered_apps


class TestFindWithSdkconfigFiles:
    def test_with_sdkconfig_defaults_idf_target(self):
        test_dir = str(IDF_PATH / 'examples')
        apps = find_apps(test_dir, 'esp32', recursive=True)
        assert apps

        # write the first app without sdkconfig.defaults with CONFIG_IDF_TARGET="linux" in sdkconfig.defaults
        _app = None
        _default_sdkconfig_path = None
        for app in apps:
            default_sdkconfig_path = os.path.join(app.app_dir, DEFAULT_SDKCONFIG)
            if not os.path.isfile(default_sdkconfig_path):
                with open(default_sdkconfig_path, 'w') as fw:
                    fw.write('CONFIG_IDF_TARGET="linux"')
                    logging.info('Created temp %s %s', DEFAULT_SDKCONFIG, default_sdkconfig_path)
                _app = app
                _default_sdkconfig_path = default_sdkconfig_path
                break
        else:
            raise ValueError('no app without {}'.format(DEFAULT_SDKCONFIG))

        try:
            filtered_apps = find_apps(test_dir, 'esp32', recursive=True)
            assert set(apps) - set(filtered_apps) == {_app}
        finally:
            try:
                os.remove(_default_sdkconfig_path)
                logging.info('Removed temp %s %s', DEFAULT_SDKCONFIG, _default_sdkconfig_path)
            except:  # noqa
                pass

    def test_with_config_rules(self, tmp_path):
        create_project('test1', tmp_path)

        (tmp_path / 'test1' / 'sdkconfig.defaults').touch()
        (tmp_path / 'test1' / 'sdkconfig.defaults_new').touch()
        (tmp_path / 'test1' / 'sdkconfig.ci.foo').touch()

        apps = find_apps(str(tmp_path / 'test1'), 'esp32', recursive=True, config_rules_str='sdkconfig.ci.*=')
        assert len(apps) == 1
        assert apps[0].sdkconfig_files == [
            str(tmp_path / 'test1' / 'sdkconfig.defaults'),
            str(tmp_path / 'test1' / 'sdkconfig.ci.foo'),
        ]

        os.environ['SDKCONFIG_DEFAULTS'] = 'sdkconfig.defaults_new'
        apps = find_apps(str(tmp_path / 'test1'), 'esp32', recursive=True, config_rules_str='sdkconfig.ci.*=')
        assert len(apps) == 1
        assert apps[0].sdkconfig_files == [
            str(tmp_path / 'test1' / 'sdkconfig.defaults_new'),
            str(tmp_path / 'test1' / 'sdkconfig.ci.foo'),
        ]

        apps = find_apps(
            str(tmp_path),
            'esp32',
            recursive=True,
            config_rules_str='sdkconfig.ci.*=',  # wrong one
            sdkconfig_defaults='notexists;sdkconfig.defaults_new;sdkconfig.defaults',
        )
        assert len(apps) == 1
        assert apps[0].sdkconfig_files == [
            str(tmp_path / 'test1' / 'sdkconfig.defaults_new'),
            str(tmp_path / 'test1' / 'sdkconfig.defaults'),
            str(tmp_path / 'test1' / 'sdkconfig.ci.foo'),
        ]

    def test_with_sdkconfig_defaults_env_var_expansion(self, tmp_path, monkeypatch):
        create_project('test1', tmp_path)
        (tmp_path / 'test1' / 'sdkconfig.ci.foo').write_text('CONFIG_IDF_TARGET=${TEST_TARGET}', encoding='utf8')
        (tmp_path / 'test1' / 'sdkconfig.ci.bar').write_text('CONFIG_IDF_TARGET=esp32s2', encoding='utf8')
        (tmp_path / 'test1' / 'sdkconfig.ci.baz').write_text('CONFIG_IDF_TARGET=esp32s3', encoding='utf8')

        monkeypatch.setenv('TEST_TARGET', 'esp32')
        apps = find_apps(str(tmp_path), 'esp32', recursive=True, config_rules_str='sdkconfig.ci.*=')
        assert len(apps) == 1
        assert Path(apps[0].sdkconfig_files[0]).parts[-2:] == ('expanded_sdkconfig_files', 'sdkconfig.ci.foo')

        # test relative paths
        os.chdir(str(tmp_path))
        apps = find_apps('test1', 'esp32', recursive=True, config_rules_str='sdkconfig.ci.*=')
        assert len(apps) == 1
        assert Path(apps[0].sdkconfig_files[0]).parts[-2:] == ('expanded_sdkconfig_files', 'sdkconfig.ci.foo')

        monkeypatch.setenv('TEST_TARGET', 'esp32s2')
        apps = find_apps('test1', 'esp32', recursive=True, config_rules_str='sdkconfig.ci.*=')
        assert len(apps) == 0
