# SPDX-FileCopyrightText: 2022-2023 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import fnmatch
import logging
import os
import shutil
import subprocess
import sys
from copy import (
    deepcopy,
)
from pathlib import (
    Path,
)

from . import (
    LOGGER,
)
from .log import (
    ColoredFormatter,
)

try:
    import typing as t
except ImportError:
    pass


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


def config_rules_from_str(rule_strings):  # type: (list[str] | str) -> list[ConfigRule]
    """
    Helper function to convert strings like 'file_name=config_name' into `ConfigRule` objects

    :param rule_strings: list of rules as strings or a single rule string
    :type rule_strings: list[str] | str
    :return: list of ConfigRules
    :rtype: list[ConfigRule]
    """
    if not rule_strings:
        return []

    rules = []
    for rule_str in to_list(rule_strings):
        items = rule_str.split('=', 2)
        rules.append(ConfigRule(items[0], items[1] if len(items) == 2 else None))
    # '' is the default config, sort this one to the front
    return sorted(rules, key=lambda x: x.file_name)


def setup_logging(verbose=0, log_file=None, colored=True):  # type: (int, str | None, bool) -> None
    """
    Setup logging stream handler

    :param verbose: 0 - WARNING, 1 - INFO, 2+ - DEBUG
    :type verbose: int
    :param log_file: log file path
    :type log_file: str
    :param colored: colored output or not
    :type colored: bool
    :return: None
    :rtype: None
    """
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
    handler.setFormatter(ColoredFormatter(colored))
    LOGGER.handlers = [handler]
    LOGGER.propagate = False


def get_parallel_start_stop(total, parallel_count, parallel_index):  # type: (int, int, int) -> (int, int)
    """
    Calculate the start and stop indices for a parallel task (1-based).

    :param total: total number of tasks
    :type total: int
    :param parallel_count: number of parallel tasks to run
    :type parallel_count: int
    :param parallel_index: index of the parallel task to run
    :type parallel_index: int
    :return: start and stop indices, [start, stop]
    :rtype: (int, int)
    """
    if parallel_count == 1:
        return 1, total

    num_builds_per_job = (total + parallel_count - 1) // parallel_count

    _min = num_builds_per_job * (parallel_index - 1) + 1
    _max = min(num_builds_per_job * parallel_index, total)

    return _min, _max


class BuildError(RuntimeError):
    pass


class InvalidCommand(SystemExit):
    def __init__(self, msg):
        super(InvalidCommand, self).__init__('Invalid Command: ' + msg.strip())


def rmdir(path, exclude_file_patterns=None):
    if not exclude_file_patterns:
        shutil.rmtree(path, ignore_errors=True)
        return

    for root, dirs, files in os.walk(path, topdown=False):
        for f in files:
            fp = os.path.join(root, f)
            remove = True
            for pattern in to_list(exclude_file_patterns):
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


def subprocess_run(
    cmd,  # type: list[str]
    log_terminal=True,  # type: bool
    log_fs=None,  # type: t.TextIO | None
    check=False,  # type: bool
    additional_env_dict=None,  # type: dict[str, any] | None
):  # type: (...) -> int
    """
    Subprocess.run for older python versions

    :param cmd: cmd
    :type cmd: list[str]
    :param log_terminal: print to `sys.stdout` if set to `True`
    :type log_terminal: bool
    :param log_fs: write to this file stream if not `None`
    :type log_fs: TextIO
    :param check: raise `BuildError` when return code is non-zero
    :type check: bool
    :param additional_env_dict: additional environment variables
    :type additional_env_dict: dict[str, any] | None
    :return: return code
    :rtype: int
    """
    LOGGER.debug('==> Running %s', ' '.join(cmd))

    subprocess_env = None
    if additional_env_dict is not None:
        subprocess_env = deepcopy(os.environ)
        subprocess_env.update(additional_env_dict)

    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=subprocess_env)
    for line in p.stdout:
        if isinstance(line, bytes):
            line = line.decode('utf-8')

        if log_terminal:
            sys.stdout.write(line)

        if log_fs:
            log_fs.write(line)

    returncode = p.wait()
    if check and returncode != 0:
        raise BuildError('Command {} returned non-zero exit status {}'.format(cmd, returncode))

    return returncode


def to_list(s):
    """
    Turn all objects to lists

    :param s: anything
    :type s: any
    :return: ``list(s)``, if ``s`` is a tuple or a set
    :return: itself, if ``s`` is a list
    :return: ``[s]``, if ``s`` is other type
    :return: ``None``, if ``s`` is None
    :rtype: list | None
    """
    if s is None:
        return s

    if isinstance(s, set) or isinstance(s, tuple):
        return list(s)
    elif isinstance(s, list):
        return s
    else:
        return [s]


def to_absolute_path(s, rootpath=None):  # type: (str, str | None) -> Path
    rp = Path(rootpath or '.').expanduser().resolve()

    sp = Path(s).expanduser()
    if sp.is_absolute():
        return sp.resolve()
    else:
        return (rp / sp).resolve()


def files_matches_patterns(
    files,  # type: list[str] | str
    patterns,  # type: list[str] | str
    rootpath=None,  # type: str
):  # type: (...) -> bool
    # can't match a absolute pattern with a relative path
    # change all to absolute paths
    files = [to_absolute_path(f, rootpath) for f in to_list(files)]
    patterns = [to_absolute_path(p, rootpath) for p in to_list(patterns)]

    for f in files:
        for p in patterns:
            if f.match(str(p)):
                return True

    return False
