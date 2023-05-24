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
        'modified_components, could_find_apps',
        [
            (None, True),
            ([], False),
            ('fake', False),
            ('soc', True),
            (['soc', 'fake'], True),
        ],
    )
    def test_with_depends_and_modified_components(self, tmpdir, modified_components, could_find_apps):
        test_dir = str(IDF_PATH / 'examples')
        apps = find_apps(test_dir, 'esp32', recursive=True)
        assert apps

        yaml_file = tmpdir / 'test.yml'
        yaml_file.write_text(
            f'''
{test_dir}:
    depends_components:
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
            modified_components=modified_components,
        )
        if could_find_apps:
            assert filtered_apps == apps
        else:
            assert not filtered_apps

    @pytest.mark.parametrize(
        'modified_files, could_find_apps',
        [
            ('/foo', False),
            (str(IDF_PATH / 'examples' / 'README.md'), False),
            ([str(IDF_PATH / 'examples' / 'get-started' / 'hello_world' / 'a.md')], False),
            (
                [
                    str(IDF_PATH / 'examples' / 'get-started' / 'hello_world' / 'a.md'),
                    str(IDF_PATH / 'examples' / 'get-started' / 'hello_world' / 'a.c'),
                ],
                True,
            ),
        ],
    )
    def test_with_depends_components_but_modified(self, tmp_path, modified_files, could_find_apps):
        test_dir = str(IDF_PATH / 'examples' / 'get-started' / 'hello_world')
        apps = find_apps(test_dir, 'esp32', recursive=True)
        assert apps

        yaml_file = tmp_path / 'test.yml'
        yaml_file.write_text(
            f'''
{test_dir}:
    depends_components:
        - soc
''',
            encoding='utf8',
        )

        filtered_apps = find_apps(
            test_dir,
            'esp32',
            recursive=True,
            manifest_files=yaml_file,
            modified_components=[],
            modified_files=modified_files,
        )
        if could_find_apps:
            assert filtered_apps == apps
        else:
            assert not filtered_apps

    @pytest.mark.parametrize(
        'modified_components, modified_files, could_find_apps',
        [
            ([], '/foo', True),
            ([], str(IDF_PATH / 'examples' / 'README.md'), False),
            (None, [str(IDF_PATH / 'examples' / 'get-started' / 'hello_world' / 'a.md')], True),
            (
                [],
                [
                    str(IDF_PATH / 'examples' / 'get-started' / 'hello_world' / 'a.md'),
                    str(IDF_PATH / 'examples' / 'get-started' / 'hello_world' / 'a.c'),
                ],
                True,
            ),
        ],
    )
    def test_with_depends_filepatterns(self, tmp_path, modified_components, modified_files, could_find_apps):
        test_dir = str(IDF_PATH / 'examples' / 'get-started' / 'hello_world')
        apps = find_apps(test_dir, 'esp32', recursive=True)
        assert apps

        yaml_file = tmp_path / 'test.yml'
        yaml_file.write_text(
            f'''
{test_dir}:
    depends_filepatterns:
        - /foo
        - examples/get-started/hello_world/**
        - examples/foo/**
''',
            encoding='utf8',
        )

        filtered_apps = find_apps(
            test_dir,
            'esp32',
            recursive=True,
            manifest_rootpath=str(IDF_PATH),
            manifest_files=yaml_file,
            modified_components=modified_components,
            modified_files=modified_files,
        )
        if could_find_apps:
            assert filtered_apps == apps
        else:
            assert not filtered_apps

    @pytest.mark.parametrize(
        'modified_files, could_find_apps',
        [
            (None, True),
            (str(IDF_PATH / 'examples' / 'README.md'), True),
            ([str(IDF_PATH / 'examples' / 'get-started' / 'hello_world' / 'a.md')], True),
            (
                [
                    str(IDF_PATH / 'examples' / 'get-started' / 'hello_world' / 'a.md'),
                    str(IDF_PATH / 'examples' / 'get-started' / 'hello_world' / 'a.c'),
                ],
                True,
            ),
            ([str(IDF_PATH / 'examples' / 'a.c')], True),
        ],
    )
    def test_with_filepattern_but_calculate_component_later(self, modified_files, could_find_apps):
        test_dir = str(IDF_PATH / 'examples' / 'get-started' / 'hello_world')
        apps = find_apps(test_dir, 'esp32', recursive=True)
        assert apps

        filtered_apps = find_apps(
            test_dir,
            'esp32',
            recursive=True,
            modified_files=modified_files,
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

    def test_with_config_rules(self, tmp_path, monkeypatch):
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

        monkeypatch.setenv('SDKCONFIG_DEFAULTS', 'sdkconfig.defaults_new')
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
        assert Path(apps[0].sdkconfig_files[0]).parts[-3:] == ('expanded_sdkconfig_files', 'build', 'sdkconfig.ci.foo')

        # test relative paths
        os.chdir(str(tmp_path))
        apps = find_apps('test1', 'esp32', recursive=True, config_rules_str='sdkconfig.ci.*=', build_dir='build_@t_@w')
        assert len(apps) == 1
        assert Path(apps[0].sdkconfig_files[0]).parts[-3:] == (
            'expanded_sdkconfig_files',
            'build_esp32_foo',
            'sdkconfig.ci.foo',
        )

        monkeypatch.setenv('TEST_TARGET', 'esp32s2')
        apps = find_apps('test1', 'esp32', recursive=True, config_rules_str='sdkconfig.ci.*=')
        assert len(apps) == 0

    def test_config_name_in_manifest(self, tmp_path):
        create_project('test1', tmp_path)

        (tmp_path / 'test1' / 'sdkconfig.defaults').touch()
        (tmp_path / 'test1' / 'sdkconfig.ci').touch()
        (tmp_path / 'test1' / 'sdkconfig.ci.foo').touch()
        (tmp_path / 'test1' / 'sdkconfig.ci.bar').touch()

        yaml_file = tmp_path / 'test.yml'
        yaml_file.write_text(
            f'''
{tmp_path}:
    enable:
    - if: CONFIG_NAME == "foo" and IDF_TARGET == "esp32"
    - if: CONFIG_NAME == "bar" and IDF_TARGET == "esp32s2"
    - if: CONFIG_NAME == "default" and IDF_TARGET == "esp32s3"
''',
            encoding='utf8',
        )

        apps = find_apps(
            str(tmp_path / 'test1'),
            'esp32',
            recursive=True,
            config_rules_str=['sdkconfig.ci.*=', 'sdkconfig.ci=default'],
            manifest_files=yaml_file,
        )
        assert len(apps) == 1
        assert apps[0].sdkconfig_files == [
            str(tmp_path / 'test1' / 'sdkconfig.defaults'),
            str(tmp_path / 'test1' / 'sdkconfig.ci.foo'),
        ]
        apps = find_apps(
            str(tmp_path / 'test1'),
            'esp32s2',
            recursive=True,
            config_rules_str=['sdkconfig.ci.*=', 'sdkconfig.ci=default'],
            manifest_files=yaml_file,
        )
        assert len(apps) == 1
        assert apps[0].sdkconfig_files == [
            str(tmp_path / 'test1' / 'sdkconfig.defaults'),
            str(tmp_path / 'test1' / 'sdkconfig.ci.bar'),
        ]
        apps = find_apps(
            str(tmp_path / 'test1'),
            'esp32s3',
            recursive=True,
            config_rules_str=['sdkconfig.ci.*=', 'sdkconfig.ci=default'],
            manifest_files=yaml_file,
        )
        assert len(apps) == 1
        assert apps[0].sdkconfig_files == [
            str(tmp_path / 'test1' / 'sdkconfig.defaults'),
            str(tmp_path / 'test1' / 'sdkconfig.ci'),
        ]
        apps = find_apps(
            str(tmp_path / 'test1'), 'esp32s3', recursive=True, config_rules_str=['=default'], manifest_files=yaml_file
        )
        assert len(apps) == 1
        assert apps[0].sdkconfig_files == [
            str(tmp_path / 'test1' / 'sdkconfig.defaults'),
        ]

    def test_env_var(self, tmp_path, monkeypatch):
        create_project('test1', tmp_path)

        (tmp_path / 'test1' / 'sdkconfig.ci.foo').touch()
        (tmp_path / 'test1' / 'sdkconfig.ci.bar').touch()
        (tmp_path / 'test1' / 'sdkconfig.ci.baz').touch()

        yaml_file = tmp_path / 'test.yml'
        yaml_file.write_text(
            f'''
{tmp_path}:
  enable:
    - if: CONFIG_NAME == "foo" and IDF_TARGET == "esp32"
    - if: CONFIG_NAME == "bar" and IDF_TARGET == "esp32s2"
    - if: TEST_ENV_VAR == "1"
    - if: CONFIG_NAME == "baz" and TEST_ENV_VAR == 0
''',
            encoding='utf8',
        )

        # in case you set it...
        monkeypatch.delenv('CONFIG_NAME', raising=False)
        monkeypatch.delenv('TEST_ENV_VAR', raising=False)

        # CONFIG_NAME should NOT be overridden by env var
        monkeypatch.setenv('CONFIG_NAME', 'bar')
        apps = find_apps(
            str(tmp_path / 'test1'),
            'esp32',
            config_rules_str=['sdkconfig.ci=default', 'sdkconfig.ci.*='],
            manifest_files=yaml_file,
        )
        assert len(apps) == 2
        assert apps[0].sdkconfig_files == [
            str(tmp_path / 'test1' / 'sdkconfig.ci.baz'),
        ]
        assert apps[1].sdkconfig_files == [
            str(tmp_path / 'test1' / 'sdkconfig.ci.foo'),
        ]
        monkeypatch.delenv('CONFIG_NAME')

        # env var should be expanded
        monkeypatch.setenv('TEST_ENV_VAR', '1')
        apps = find_apps(
            str(tmp_path / 'test1'),
            'esp32',
            config_rules_str=['sdkconfig.ci=default', 'sdkconfig.ci.*='],
            manifest_files=yaml_file,
        )
        assert len(apps) == 3
        monkeypatch.delenv('TEST_ENV_VAR')
