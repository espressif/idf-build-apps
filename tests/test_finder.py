# SPDX-FileCopyrightText: 2022 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import inspect

from idf_build_apps.constants import IDF_PATH
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
