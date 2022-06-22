# SPDX-FileCopyrightText: 2022 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import inspect

from idf_build_apps.app import App
from idf_build_apps.constants import IDF_PATH
from idf_build_apps.finder import find_apps
from idf_build_apps.manifest.manifest import Manifest


def test_finder(tmpdir):
    apps = find_apps(IDF_PATH / 'examples', 'esp32', recursive=True)
    assert apps

    yaml_file = tmpdir / 'test.yml'
    with open(yaml_file, 'w') as fw:
        fw.write(
            inspect.cleandoc(
                f'''
            {str(IDF_PATH / 'examples')}:
                enable:
                    - if: IDF_TARGET == "esp32s2"
        '''
            )
        )

    manifest = Manifest.from_file(yaml_file)
    App.MANIFEST = manifest

    filtered_apps = find_apps(IDF_PATH / 'examples', 'esp32', recursive=True)
    assert not filtered_apps
    assert filtered_apps != apps
