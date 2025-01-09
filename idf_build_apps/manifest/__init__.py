# SPDX-FileCopyrightText: 2022-2025 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

"""
Manifest file
"""

from esp_bool_parser import register_addition_attribute

from .manifest import FolderRule


def folder_rule_attr(target, **kwargs):
    return 1 if target in FolderRule.DEFAULT_BUILD_TARGETS else 0


register_addition_attribute('INCLUDE_DEFAULT', folder_rule_attr)
