# SPDX-FileCopyrightText: 2022-2024 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0
import os

import pytest

import idf_build_apps
from idf_build_apps import (
    App,
    setup_logging,
)
from idf_build_apps.manifest.manifest import FolderRule


@pytest.fixture(autouse=True)
def clean_cls_attr():
    App.MANIFEST = None
    idf_build_apps.SESSION_ARGS.clean()


@pytest.fixture(autouse=True)
def setup_logging_debug():
    setup_logging(1)


def create_project(name, folder):
    p = str(folder / name)
    os.makedirs(p)
    os.makedirs(os.path.join(p, 'main'))

    with open(os.path.join(p, 'CMakeLists.txt'), 'w') as fw:
        fw.write(
            f"""cmake_minimum_required(VERSION 3.16)
include($ENV{{IDF_PATH}}/tools/cmake/project.cmake)
project({name})
"""
        )

    with open(os.path.join(p, 'main', 'CMakeLists.txt'), 'w') as fw:
        fw.write(
            f"""idf_component_register(SRCS "{name}.c"
INCLUDE_DIRS ".")
"""
        )

    with open(os.path.join(p, 'main', f'{name}.c'), 'w') as fw:
        fw.write(
            """#include <stdio.h>
void app_main(void) {}
"""
        )


@pytest.fixture
def sha_of_enable_only_esp32():
    sha = FolderRule('test1', enable=[{'if': 'IDF_TARGET == "esp32"'}]).sha

    # !!! ONLY CHANGE IT WHEN NECESSARY !!!
    assert (
        sha
        == '6fd3175a5068c46bccc411efadf3b98314210e775c25c62833998bff8b0cf1bc1daf738326f138f0d6629caa07338428f2aa122e2b830e6ad43662057c7ea0b1'  # noqa: E501
    )

    return sha
