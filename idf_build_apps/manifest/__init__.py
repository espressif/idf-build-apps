# SPDX-FileCopyrightText: 2022-2025 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

"""
Manifest file
"""

from .manifest import DEFAULT_BUILD_TARGETS, FolderRule

__all__ = [
    'DEFAULT_BUILD_TARGETS',
    'FolderRule',
]

from esp_bool_parser import register_addition_attribute


def folder_rule_attr(target, **kwargs):
    return 1 if target in DEFAULT_BUILD_TARGETS.get() else 0


register_addition_attribute('INCLUDE_DEFAULT', folder_rule_attr)
