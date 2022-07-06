# SPDX-FileCopyrightText: 2022 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import fnmatch
import logging
import os
import re
import shutil
import sys

from . import LOGGER

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


def setup_logging(verbose=0, log_file=None):  # type: (int, str | None) -> None
    if not verbose:
        level = logging.WARNING
    elif verbose == 1:
        level = logging.INFO
    else:
        level = logging.DEBUG

    LOGGER.setLevel(level)
    if log_file:
        stream = open(log_file, 'w')
    else:
        stream = sys.stderr
    handler = logging.StreamHandler(stream)
    handler.setLevel(level)
    handler.setFormatter(
        logging.Formatter(
            '%(asctime)s %(levelname)s %(message)s', datefmt='%Y-%m-%d %H:%M:%S'
        )
    )

    LOGGER.handlers = [handler]
    LOGGER.propagate = False


def get_parallel_start_stop(
    total, parallel_count, parallel_index
):  # type: (int, int, int) -> (int, int)
    """
    Calculate the start and stop indices for a parallel task (1-based).

    :param total: total number of tasks
    :param parallel_count: number of parallel tasks to run
    :param parallel_index: index of the parallel task
    :return: start and stop indices
    """
    if parallel_count == 1:
        return 1, total

    num_builds_per_job = (total + parallel_count - 1) // parallel_count

    _min = num_builds_per_job * (parallel_index - 1) + 1
    _max = min(num_builds_per_job * parallel_index, total)

    return _min, _max


class BuildError(RuntimeError):
    pass


def rmdir(path, exclude_file_patterns=None):
    if not exclude_file_patterns:
        shutil.rmtree(path, ignore_errors=True)
        return

    if isinstance(exclude_file_patterns, str):
        exclude_file_patterns = [exclude_file_patterns]

    for root, dirs, files in os.walk(path, topdown=False):
        for f in files:
            fp = os.path.join(root, f)
            remove = True
            for pattern in exclude_file_patterns:
                if pattern and fnmatch.fnmatch(f, pattern):
                    remove = False
                    break
            if remove:
                os.remove(fp)
        for d in dirs:
            try:
                os.rmdir(os.path.join(root, d))
            except OSError:
                pass


def find_first_match(pattern, path):
    for root, _, files in os.walk(path):
        res = fnmatch.filter(files, pattern)
        if res:
            return os.path.join(root, res[0])
    return None
