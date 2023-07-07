# SPDX-FileCopyrightText: 2022-2023 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0
import os

import pytest

from idf_build_apps import (
    CONFIG,
    setup_logging,
)


@pytest.fixture(autouse=True)
def clean_cls_attr():
    CONFIG.reset_and_config()


@pytest.fixture(autouse=True)
def setup_logging_debug():
    setup_logging(1)


def create_project(name, folder):
    p = str(folder / name)
    os.makedirs(p)
    os.makedirs(os.path.join(p, 'main'))

    with open(os.path.join(p, 'CMakeLists.txt'), 'w') as fw:
        fw.writelines(
            [
                'cmake_minimum_required(VERSION 3.16)',
                'include($ENV{IDF_PATH}/tools/cmake/project.cmake)',
                f'project({name})',
            ]
        )

    with open(os.path.join(p, 'main', 'CMakeLists.txt'), 'w') as fw:
        fw.writelines(
            [
                f'idf_component_register(SRCS "{name}.c"',
                '    INCLUDE_DIRS ".")',
            ]
        )

    with open(os.path.join(p, 'main', f'{name}.c'), 'w') as fw:
        fw.writelines(
            [
                '#include <stdio.h>',
                'void app_main(void) {}',
            ]
        )
