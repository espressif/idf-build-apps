# SPDX-FileCopyrightText: 2022 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import inspect

from idf_build_apps.manifest.manifest import Manifest


def test_manifest(tmpdir):
    yaml_file = tmpdir / 'test.yml'
    with open(yaml_file, 'w') as fw:
        fw.write(
            inspect.cleandoc(
                '''
            test1:
                enable:
                    - if: IDF_TARGET == "esp32" or IDF_TARGET == "esp32c3"
                disable_test:
                    - if: IDF_TARGET == "esp32c3"
        '''
            )
        )

    manifest = Manifest.from_file(yaml_file)

    assert manifest.enable_build_targets('test1') == ['esp32', 'esp32c3']
    assert manifest.enable_test_targets('test1') == ['esp32']
