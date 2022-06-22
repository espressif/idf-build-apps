# SPDX-FileCopyrightText: 2022 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import re

_SDKCONFIG_KV_RE = re.compile(r'^([^#=]+)=(.+)$')


def dict_from_sdkconfig(path):  # type: (str) -> dict[str, str]
    """
    Parse the sdkconfig file at 'path', return name:value pairs as a dict
    """
    result = {}
    with open(path) as f:
        for line in f:
            m = _SDKCONFIG_KV_RE.match(line)
            if m:
                val = m.group(2)
                if val.startswith('"') and val.endswith('"'):
                    val = val[1:-1]
                result[m.group(1)] = val
    return result


class ConfigRule:
    def __init__(self, file_name, config_name):  # type: (str, str) -> None
        """
        ConfigRule represents the sdkconfig file and the config name.

        For example:
            - filename='', config_name='default' — represents the default app configuration, and gives it a name
                'default'
            - filename='sdkconfig.*', config_name=None - represents the set of configurations, names match the wildcard
                value

        :param file_name: name of the sdkconfig file fragment, optionally with a single wildcard ('*' character).
            can also be empty to indicate that the default configuration of the app should be used
        :param config_name: name of the corresponding build configuration, or None if the value of wildcard is to be
            used
        """

        self.file_name = file_name
        self.config_name = config_name


def config_rules_from_str(rule_strings):  # type: (list[str]) -> list[ConfigRule]
    """
    Helper function to convert strings like 'file_name=config_name' into ConfigRule objects

    :param rule_strings: list of rules as strings
    :return: list of ConfigRules
    """
    if not rule_strings:
        return []

    rules = []
    for rule_str in rule_strings:
        items = rule_str.split('=', 2)
        rules.append(ConfigRule(items[0], items[1] if len(items) == 2 else None))
    # '' is the default config, sort this one to the front
    return sorted(rules, key=lambda x: x.file_name)
