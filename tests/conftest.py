# SPDX-FileCopyrightText: 2022-2024 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0
import os

import pytest

import idf_build_apps
from idf_build_apps import (
    App,
    setup_logging,
)
from idf_build_apps.args import apply_config_file
from idf_build_apps.constants import IDF_BUILD_APPS_TOML_FN, SUPPORTED_TARGETS
from idf_build_apps.manifest.manifest import FolderRule


@pytest.fixture(autouse=True)
def clean_cls_attr(tmp_path):
    App.MANIFEST = None
    FolderRule.DEFAULT_BUILD_TARGETS = SUPPORTED_TARGETS
    idf_build_apps.SESSION_ARGS.clean()
    apply_config_file(IDF_BUILD_APPS_TOML_FN)
    os.chdir(tmp_path)


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


@pytest.fixture
def sha_of_enable_esp32_or_esp32s2():
    sha = FolderRule('test1', enable=[{'if': 'IDF_TARGET == "esp32" or IDF_TARGET == "esp32s2"'}]).sha

    # !!! ONLY CHANGE IT WHEN NECESSARY !!!
    assert (
        sha
        == 'f3408e9bf1d6b9a9e14559e6567917986678a3414229b29f96493aec4dc1bc3e6d0ecc4f79adced0d5c26bc1cd80a4d15fe6aaefa5d1e7033a58290374f4fc7f'  # noqa: E501
    )

    return sha
