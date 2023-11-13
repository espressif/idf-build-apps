# SPDX-FileCopyrightText: 2022-2023 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0
import os

import pytest

from idf_build_apps import (
    App,
    setup_logging,
)


@pytest.fixture(autouse=True)
def clean_cls_attr():
    App.MANIFEST = None


@pytest.fixture(autouse=True)
def setup_logging_debug():
    setup_logging(1)


def create_project(name, folder):
    p = str(folder / name)
    os.makedirs(p)
    os.makedirs(os.path.join(p, 'main'))

    with open(os.path.join(p, 'CMakeLists.txt'), 'w') as fw:
        fw.write(
            """cmake_minimum_required(VERSION 3.16)
include($ENV{{IDF_PATH}}/tools/cmake/project.cmake)
project({})
""".format(
                name
            )
        )

    with open(os.path.join(p, 'main', 'CMakeLists.txt'), 'w') as fw:
        fw.write(
            """idf_component_register(SRCS "{}.c"
INCLUDE_DIRS ".")
""".format(
                name
            )
        )

    with open(os.path.join(p, 'main', f'{name}.c'), 'w') as fw:
        fw.write(
            """#include <stdio.h>
void app_main(void) {}
"""
        )
