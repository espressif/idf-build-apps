# SPDX-FileCopyrightText: 2022-2023 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import inspect
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


def test_finder(tmpdir):
    test_dir = str(IDF_PATH / 'examples')
    apps = find_apps(test_dir, 'esp32', recursive=True)
    assert apps

    yaml_file = str(tmpdir / 'test.yml')
    with open(yaml_file, 'w') as fw:
        fw.write(
            inspect.cleandoc(
                '''
            {}:
                enable:
                    - if: IDF_TARGET == "esp32s2"
        '''.format(
                    test_dir
                )
            )
        )
    filtered_apps = find_apps(test_dir, 'esp32', recursive=True, manifest_files=yaml_file)
    assert not filtered_apps
    assert filtered_apps != apps


def test_finder_with_sdkconfig_defaults():
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
                logging.info('Created temp %s %s', DEFAULT_SDKCONFIG, _default_sdkconfig_path)
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
def test_finder_with_requires_and_depends_on_components(tmpdir, depends_on_components, could_find_apps):
    test_dir = str(IDF_PATH / 'examples')
    apps = find_apps(test_dir, 'esp32', recursive=True)
    assert apps

    yaml_file = str(tmpdir / 'test.yml')
    with open(yaml_file, 'w') as fw:
        fw.write(
            inspect.cleandoc(
                '''
            {}:
                requires_components:
                    - freertos
                    - soc
        '''.format(
                    test_dir
                )
            )
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


def test_finder_after_chdir():
    test_dir = IDF_PATH / 'examples' / 'get-started'

    yaml_file = str(test_dir / 'test.yml')
    with open(yaml_file, 'w') as fw:
        fw.write(
            inspect.cleandoc(
                '''
            examples/get-started:
                enable:
                    - if: IDF_TARGET != "esp32"
        '''
            )
        )

    os.chdir(IDF_PATH)
    assert not find_apps(str(test_dir), 'esp32', recursive=True, manifest_files=yaml_file)

    # manifest folder invalid
    os.chdir(test_dir)
    assert find_apps(str(test_dir), 'esp32', recursive=True, manifest_files=yaml_file)


def test_finder_custom_root_dir():
    test_dir = IDF_PATH / 'examples' / 'get-started'

    yaml_file = str(test_dir / 'test.yml')
    with open(yaml_file, 'w') as fw:
        fw.write(
            inspect.cleandoc(
                '''
            get-started:
                enable:
                    - if: IDF_TARGET != "esp32"
        '''
            )
        )

    assert find_apps(str(test_dir), 'esp32', recursive=True, manifest_files=yaml_file, manifest_rootpath=str(IDF_PATH))

    assert not find_apps(
        str(test_dir), 'esp32', recursive=True, manifest_files=yaml_file, manifest_rootpath=str(IDF_PATH / 'examples')
    )


def test_finder_idf_version():
    test_dir = IDF_PATH / 'examples' / 'get-started'
    apps = find_apps(str(test_dir), 'esp32', recursive=True)
    assert apps

    yaml_file = str(test_dir / 'test.yml')
    with open(yaml_file, 'w') as fw:
        fw.write(
            inspect.cleandoc(
                '''
            get-started:
                enable:
                    - if: IDF_VERSION_MAJOR > 0 and IDF_VERSION_MINOR < 999 and IDF_VERSION_PATCH in [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        '''
            )
        )

    assert find_apps(str(test_dir), 'esp32', recursive=True, manifest_files=yaml_file) == apps


def test_find_apps_config_rules(tmp_path):
    create_project('test1', tmp_path)

    (Path(tmp_path) / 'test1' / 'sdkconfig.ci.foo').touch()
    (Path(tmp_path) / 'test1' / 'sdkconfig.ci.bar').touch()

    apps = find_apps(str(tmp_path), 'esp32', recursive=True, config_rules_str='sdkconfig.ci.*=')
    assert len(apps) == 2
    assert apps[0].config_name == 'bar'
    assert apps[1].config_name == 'foo'


def test_find_apps_sdkconfig_defaults(tmp_path):
    create_project('test1', tmp_path)

    (Path(tmp_path) / 'test1' / 'sdkconfig.defaults').touch()
    (Path(tmp_path) / 'test1' / 'sdkconfig.defaults_new').touch()

    apps = find_apps(str(tmp_path), 'esp32', recursive=True, config_rules_str='sdkconfig.ci.*=')
    assert len(apps) == 1
    assert apps[0].sdkconfig_defaults_list == ['sdkconfig.defaults']

    os.environ['SDKCONFIG_DEFAULTS'] = 'sdkconfig.defaults_new'
    apps = find_apps(str(tmp_path), 'esp32', recursive=True, config_rules_str='sdkconfig.ci.*=')
    assert len(apps) == 1
    assert apps[0].sdkconfig_defaults_list == ['sdkconfig.defaults_new']

    apps = find_apps(
        str(tmp_path),
        'esp32',
        recursive=True,
        config_rules_str='sdkconfig.ci.*=',  # wrong one
        sdkconfig_defaults='notexists;sdkconfig.defaults_new;sdkconfig.defaults',
    )
    assert len(apps) == 1
    assert apps[0].sdkconfig_defaults_list == ['sdkconfig.defaults_new', 'sdkconfig.defaults']
