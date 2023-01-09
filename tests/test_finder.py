# SPDX-FileCopyrightText: 2022 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import inspect
import logging
import os

from idf_build_apps.constants import DEFAULT_SDKCONFIG, IDF_PATH
from idf_build_apps.main import find_apps


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


def test_finder_with_requires_and_depends_on_components(tmpdir):
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
                    - foo
                    - bar
        '''.format(
                    test_dir
                )
            )
        )
    filtered_apps = find_apps(
        test_dir, 'esp32', recursive=True, manifest_files=yaml_file, depends_on_components=['baz']
    )
    assert not filtered_apps

    filtered_apps = find_apps(
        test_dir, 'esp32', recursive=True, manifest_files=yaml_file, depends_on_components=['bar']
    )
    assert filtered_apps == apps


def test_finder_with_requires_without_depends_on_components(tmpdir):
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
                    - foo
                    - bar
        '''.format(
                    test_dir
                )
            )
        )
    filtered_apps = find_apps(test_dir, 'esp32', recursive=True, manifest_files=yaml_file)
    assert filtered_apps == apps
