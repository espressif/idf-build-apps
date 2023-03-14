# SPDX-FileCopyrightText: 2022-2023 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import inspect
import os

from idf_build_apps.manifest.manifest import (
    Manifest,
)


def test_manifest(tmpdir):
    yaml_file = tmpdir / 'test.yml'
    with open(yaml_file, 'w') as fw:
        fw.write(
            inspect.cleandoc(
                '''
            test1:
                enable:
                    - if: IDF_TARGET == "esp32" or IDF_TARGET == "esp32c3"
                    - if: IDF_TARGET == "esp32s2" and IDF_VERSION_MAJOR in [4, 5]
                disable_test:
                    - if: IDF_TARGET == "esp32c3"
        '''
            )
        )

    os.chdir(tmpdir)
    Manifest.ROOTPATH = tmpdir
    manifest = Manifest.from_file(yaml_file)

    assert manifest.enable_build_targets('test1') == ['esp32', 'esp32c3', 'esp32s2']
    assert manifest.enable_test_targets('test1') == ['esp32', 'esp32s2']
