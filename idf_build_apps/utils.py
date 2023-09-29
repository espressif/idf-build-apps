# SPDX-FileCopyrightText: 2022-2023 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import fnmatch
import glob
import os
import shutil
import subprocess
import sys
import typing as t
from copy import (
    deepcopy,
)
from pathlib import (
    Path,
)

from packaging.version import (
    Version,
)
from pydantic import BaseModel as _BaseModel

from . import (
    LOGGER,
)


class ConfigRule:
    def __init__(self, file_name: str, config_name: t.Optional[str]) -> None:
        """
        ConfigRule represents the sdkconfig file and the config name.

        For example:
            - filename='', config_name='default' - represents the default app configuration, and gives it a name
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


def config_rules_from_str(rule_strings: t.Union[t.List[str], str]) -> t.List[ConfigRule]:
    """
    Helper function to convert strings like 'file_name=config_name' into `ConfigRule` objects

    :param rule_strings: list of rules as strings or a single rule string
    :return: list of ConfigRules
    """
    if not rule_strings:
        return []

    rules = []
    for rule_str in to_list(rule_strings):
        items = rule_str.split('=', 2)
        rules.append(ConfigRule(items[0], items[1] if len(items) == 2 else None))
    # '' is the default config, sort this one to the front
    return sorted(rules, key=lambda x: x.file_name)


def get_parallel_start_stop(total: int, parallel_count: int, parallel_index: int) -> t.Tuple[int, int]:
    """
    Calculate the start and stop indices for a parallel task (1-based).

    :param total: total number of tasks
    :param parallel_count: number of parallel tasks to run
    :param parallel_index: index of the parallel task to run
    :return: start and stop indices, [start, stop]
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
    def __init__(self, msg: str) -> None:
        super().__init__('Invalid Command: ' + msg.strip())


class InvalidInput(SystemExit):
    """Invalid input from user"""


class InvalidIfClause(SystemExit):
    """Invalid if clause in manifest file"""


class InvalidManifest(SystemExit):
    """Invalid manifest file"""


def rmdir(path: str, exclude_file_patterns: t.Union[t.List[str], str, None] = None) -> None:
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


def find_first_match(pattern: str, path: str) -> t.Optional[str]:
    for root, _, files in os.walk(path):
        res = fnmatch.filter(files, pattern)
        if res:
            return os.path.join(root, res[0])
    return None


def subprocess_run(
    cmd: t.List[str],
    log_terminal: bool = True,
    log_fs: t.Optional[t.TextIO] = None,
    check: bool = False,
    additional_env_dict: t.Optional[t.Dict[str, str]] = None,
    **kwargs,
) -> int:
    """
    Subprocess.run for older python versions

    :param cmd: cmd
    :param log_terminal: print to `sys.stdout` if set to `True`
    :param log_fs: write to this file stream if not `None`
    :param check: raise `BuildError` when return code is non-zero
    :param additional_env_dict: additional environment variables
    :return: return code
    """
    LOGGER.debug('==> Running %s', ' '.join(cmd))

    subprocess_env = None
    if additional_env_dict is not None:
        subprocess_env = deepcopy(os.environ)
        subprocess_env.update(additional_env_dict)

    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=subprocess_env, **kwargs)
    for line in p.stdout:
        if isinstance(line, bytes):
            line = line.decode('utf-8')

        if log_terminal:
            sys.stdout.write(line)

        if log_fs:
            log_fs.write(line)

    returncode = p.wait()
    if check and returncode != 0:
        raise BuildError(f'Command {cmd} returned non-zero exit status {returncode}')

    return returncode


def to_list(s: t.Any) -> t.Optional[t.List[t.Any]]:
    """
    Turn all objects to lists

    :param s: anything
    :return:
        - ``None``, if ``s`` is None
        - itself, if ``s`` is a list
        - ``list(s)``, if ``s`` is a tuple or a set
        - ``[s]``, if ``s`` is other type

    """
    if s is None:
        return s

    if isinstance(s, list):
        return s

    if isinstance(s, set) or isinstance(s, tuple):
        return list(s)

    return [s]


def to_set(s: t.Any) -> t.Optional[t.Set[t.Any]]:
    """
    Turn all objects to sets

    :param s: anything
    :return:
        - ``None``, if ``s`` is None
        - itself, if ``s`` is a set
        - ``set(to_list(s))``, if ``s`` is other type
    """
    if s is None:
        return s

    if isinstance(s, set):
        return s

    return set(to_list(s))


def to_absolute_path(s: str, rootpath: t.Optional[str] = None) -> Path:
    rp = Path(os.path.expanduser(rootpath or '.')).resolve()

    sp = Path(os.path.expanduser(s))
    if sp.is_absolute():
        return sp.resolve()
    else:
        return (rp / sp).resolve()


def to_version(s: t.Any) -> Version:
    if isinstance(s, Version):
        return s

    try:
        return Version(str(s))
    except ValueError:
        raise InvalidInput(f'Invalid version: {s}')


def files_matches_patterns(
    files: t.Union[t.List[str], str],
    patterns: t.Union[t.List[str], str],
    rootpath: t.Optional[str] = None,
) -> bool:
    # can't match an absolute pattern with a relative path
    # change all to absolute paths
    files = [to_absolute_path(f, rootpath) for f in to_list(files)]
    patterns = [to_absolute_path(p, rootpath) for p in to_list(patterns)]

    matched_paths = set()
    for pat in patterns:
        matched_paths.update(glob.glob(str(pat), recursive=True))

    for f in files:
        if str(f) in matched_paths:
            return True

    return False


class BaseModel(_BaseModel):
    """
    BaseModel that is hashable
    """

    def __lt__(self, other: t.Any) -> bool:
        if isinstance(other, self.__class__):
            for k in self.model_dump():
                if getattr(self, k) != getattr(other, k):
                    return getattr(self, k) < getattr(other, k)
                else:
                    continue

        return NotImplemented

    def __eq__(self, other: t.Any) -> bool:
        if isinstance(other, self.__class__):
            self_dict = self.model_dump()
            other_dict = other.model_dump()

            return self_dict == other_dict

        return NotImplemented

    def __hash__(self) -> int:
        hash_list = []
        for v in self.__dict__.values():
            if isinstance(v, list):
                hash_list.append(tuple(v))
            elif isinstance(v, dict):
                hash_list.append(tuple(v.items()))
            else:
                hash_list.append(v)

        return hash((type(self),) + tuple(hash_list))
