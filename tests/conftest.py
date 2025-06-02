# SPDX-FileCopyrightText: 2022-2025 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0
import os

import pytest

import idf_build_apps
from idf_build_apps import (
    App,
    setup_logging,
)
from idf_build_apps.args import apply_config_file
from idf_build_apps.manifest.manifest import FolderRule, reset_default_build_targets


@pytest.fixture(autouse=True)
def clean_cls_attr(tmp_path):
    App.MANIFEST = None
    reset_default_build_targets()
    idf_build_apps.SESSION_ARGS.clean()
    apply_config_file(reset=True)
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
        == 'bfc1c61176cfb76169eab6c4f00dbcc4d7886fee4b93ede5fac2c005dd85db640464e9b03986d3da3bfaa4d109b053862c07dc4d5a407e58f773a8f710ec60cb'  # noqa: E501
    )

    return sha


@pytest.fixture
def sha_of_enable_esp32_or_esp32s2():
    sha = FolderRule('test1', enable=[{'if': 'IDF_TARGET == "esp32" or IDF_TARGET == "esp32s2"'}]).sha

    # !!! ONLY CHANGE IT WHEN NECESSARY !!!
    assert (
        sha
        == '9ab121a0d39bcb590465837091e82dfd798cd1ff9579e92c23e8bebaee127b46751108f0de3953993cb7993903e45d78851fc465d774a606b0ab1251fbe4b9f5'  # noqa: E501
    )

    return sha
