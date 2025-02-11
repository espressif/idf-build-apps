# SPDX-FileCopyrightText: 2022-2025 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import fnmatch
import functools
import glob
import logging
import os
import shutil
import subprocess
import sys
import typing as t
from copy import (
    deepcopy,
)
from pathlib import Path

from packaging.version import (
    Version,
)
from pydantic import BaseModel as _BaseModel

LOGGER = logging.getLogger(__name__)

if sys.version_info < (3, 8):
    from typing_extensions import (
        Literal,
    )
else:
    from typing import (
        Literal,  # noqa
    )

if sys.version_info < (3, 11):
    from typing_extensions import (
        Self,
    )
else:
    from typing import (
        Self,  # noqa
    )


class ConfigRule:
    def __init__(self, file_name: str, config_name: str = '') -> None:
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


def config_rules_from_str(rule_strings: t.Optional[t.List[str]]) -> t.List[ConfigRule]:
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
        rules.append(ConfigRule(items[0], items[1] if len(items) == 2 else ''))
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


class AutocompleteActivationError(SystemExit):
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


def rmdir(path: t.Union[Path, str], exclude_file_patterns: t.Union[t.List[str], str, None] = None) -> None:
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
    log_fs: t.Union[t.IO[str], str, None] = None,
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

    def _log_stdout(fs: t.Optional[t.IO[str]] = None):
        if p.stdout:
            for line in p.stdout:
                if isinstance(line, bytes):
                    line = line.decode('utf-8')

                if log_terminal:
                    sys.stdout.write(line)

                if fs:
                    fs.write(line)

    if p.stdout:
        if log_fs:
            if isinstance(log_fs, str):
                with open(log_fs, 'a') as fa:
                    _log_stdout(fa)
            else:
                _log_stdout(log_fs)

    returncode = p.wait()
    if check and returncode != 0:
        raise BuildError(f'Command {cmd} returned non-zero exit status {returncode}')

    return returncode


_T = t.TypeVar('_T')


@t.overload
def to_list(s: None) -> None: ...


@t.overload
def to_list(s: t.Iterable[_T]) -> t.List[_T]: ...


@t.overload
def to_list(s: _T) -> t.List[_T]: ...


def to_list(s):
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


@t.overload
def to_set(s: None) -> None: ...


@t.overload
def to_set(s: t.Iterable[_T]) -> t.Set[_T]: ...


@t.overload
def to_set(s: _T) -> t.Set[_T]: ...


def to_set(s):
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


def semicolon_separated_str_to_list(s: t.Optional[str]) -> t.Optional[t.List[str]]:
    """
    Split a string by semicolon and strip each part

    Args:
        s: string to split

    Returns:
        list of strings
    """
    if s is None or s.strip() == '':
        return None

    return [p.strip() for p in s.strip().split(';') if p.strip()]


def to_absolute_path(s: str, rootpath: t.Optional[str] = None) -> str:
    rp = os.path.abspath(os.path.expanduser(rootpath or '.'))

    sp = os.path.expanduser(s)
    if os.path.isabs(sp):
        return sp
    else:
        return os.path.abspath(os.path.join(rp, sp))


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
    matched_paths = set()
    for pat in [to_absolute_path(p, rootpath) for p in to_list(patterns)]:
        matched_paths.update(glob.glob(str(pat), recursive=True))

    for f in [to_absolute_path(f, rootpath) for f in to_list(files)]:
        if str(f) in matched_paths:
            return True

    return False


@functools.total_ordering
class BaseModel(_BaseModel):
    """
    BaseModel that is hashable
    """

    __EQ_IGNORE_FIELDS__: t.List[str] = []
    __EQ_TUNE_FIELDS__: t.Dict[str, t.Callable[[t.Any], t.Any]] = {}

    def __lt__(self, other: t.Any) -> bool:
        if isinstance(other, self.__class__):
            for k in self.model_dump():
                if k in self.__EQ_IGNORE_FIELDS__:
                    continue

                self_attr = getattr(self, k, '') or ''
                other_attr = getattr(other, k, '') or ''

                if k in self.__EQ_TUNE_FIELDS__:
                    self_attr = str(self.__EQ_TUNE_FIELDS__[k](self_attr))
                    other_attr = str(self.__EQ_TUNE_FIELDS__[k](other_attr))

                if self_attr != other_attr:
                    return self_attr < other_attr

                continue

            return False

        return NotImplemented

    def __eq__(self, other: t.Any) -> bool:
        if isinstance(other, self.__class__):
            # we only care the public attributes
            self_model_dump = self.model_dump()
            other_model_dump = other.model_dump()

            for _field in self.__EQ_IGNORE_FIELDS__:
                self_model_dump.pop(_field, None)
                other_model_dump.pop(_field, None)

            for _field in self.__EQ_TUNE_FIELDS__:
                self_model_dump[_field] = self.__EQ_TUNE_FIELDS__[_field](self_model_dump[_field])
                other_model_dump[_field] = self.__EQ_TUNE_FIELDS__[_field](other_model_dump[_field])

            return self_model_dump == other_model_dump

        return NotImplemented

    def __hash__(self) -> int:
        hash_list = []

        self_model_dump = self.model_dump()
        for _field in self.__EQ_TUNE_FIELDS__:
            self_model_dump[_field] = self.__EQ_TUNE_FIELDS__[_field](self_model_dump[_field])

        for v in self_model_dump.values():
            if isinstance(v, list):
                hash_list.append(tuple(v))
            elif isinstance(v, dict):
                hash_list.append(tuple(v.items()))
            else:
                hash_list.append(v)

        return hash((type(self), *tuple(hash_list)))


def drop_none_kwargs(d: dict) -> dict:
    return {k: v for k, v in d.items() if v is not None}


PathLike = t.Union[str, Path]
