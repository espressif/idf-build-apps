# SPDX-FileCopyrightText: 2022-2024 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0
import logging
import os
import pickle
import typing as t
from hashlib import sha512

from pyparsing import (
    ParseException,
)

from ..constants import (
    ALL_TARGETS,
    SUPPORTED_TARGETS,
)
from ..utils import (
    InvalidIfClause,
    InvalidManifest,
    to_absolute_path,
)
from ..yaml import (
    parse,
)
from .if_parser import (
    BOOL_EXPR,
    BoolStmt,
)

LOGGER = logging.getLogger(__name__)


class IfClause:
    def __init__(self, stmt: str, temporary: bool = False, reason: t.Optional[str] = None) -> None:
        try:
            self.stmt: BoolStmt = BOOL_EXPR.parseString(stmt)[0]
        except ParseException:
            raise InvalidIfClause(f'Invalid if statement: {stmt}')

        self.temporary = temporary
        self.reason = reason

        if self.temporary is True and not self.reason:
            raise InvalidIfClause('"reason" must be set when "temporary: true"')

    def get_value(self, target: str, config_name: str) -> t.Any:
        return self.stmt.get_value(target, config_name)


class SwitchClause:
    def __init__(
        self, if_clauses: t.List[IfClause], contents: t.List[t.List[str]], default_clause: t.List[str]
    ) -> None:
        self.if_clauses = if_clauses
        self.contents = contents
        self.default_clause = default_clause

    def get_value(self, target: str, config_name: str) -> t.Any:
        for if_clause, content in zip(self.if_clauses, self.contents):
            if if_clause.get_value(target, config_name):
                return content
        return self.default_clause


class FolderRule:
    DEFAULT_BUILD_TARGETS = SUPPORTED_TARGETS

    def __init__(
        self,
        folder: str,
        enable: t.Optional[t.List[t.Dict[str, t.Any]]] = None,
        disable: t.Optional[t.List[t.Dict[str, t.Any]]] = None,
        disable_test: t.Optional[t.List[t.Dict[str, t.Any]]] = None,
        depends_components: t.Optional[t.List[t.Union[str, t.Dict[str, t.Any]]]] = None,
        depends_filepatterns: t.Optional[t.List[t.Union[str, t.Dict[str, t.Any]]]] = None,
    ) -> None:
        self.folder = os.path.abspath(folder)

        def _clause_to_if_clause(clause: t.Dict[str, t.Any]) -> IfClause:
            _kwargs = {'stmt': clause['if']}
            if 'temporary' in clause:
                _kwargs['temporary'] = clause['temporary']
            if 'reason' in clause:
                _kwargs['reason'] = clause['reason']
            return IfClause(**_kwargs)

        def _clause_to_switch_or_list(
            statements: t.Optional[t.List[t.Union[str, t.Dict[str, t.Any]]]],
        ) -> t.Union[SwitchClause, t.List[str]]:
            if not statements:
                return []

            switch_statements = []
            str_statements = []
            for statement in statements:
                if isinstance(statement, t.Dict):
                    switch_statements.append(statement)
                else:
                    str_statements.append(statement)

            if switch_statements and str_statements:
                raise InvalidManifest('Current manifest format has to fit either the switch format or the list format.')

            if str_statements:
                return str_statements

            return _clause_to_switch_clause(switch_statements)

        def _clause_to_switch_clause(switch_statements: t.List[t.Dict[str, t.Any]]) -> SwitchClause:
            if_clauses = []
            contents = []
            default_clauses = []
            for statement in switch_statements:
                if 'if' in statement:
                    if_clauses.append(IfClause(stmt=statement['if']))
                    contents.append(statement['content'])
                elif 'default' in statement:
                    default_clauses.extend(statement['default'])
                else:
                    raise InvalidManifest("Only the 'if' and 'default' keywords are supported in switch clause.")

            return SwitchClause(if_clauses, contents, default_clauses)

        self.enable = [_clause_to_if_clause(clause) for clause in enable] if enable else []
        self.disable = [_clause_to_if_clause(clause) for clause in disable] if disable else []
        self.disable_test = [_clause_to_if_clause(clause) for clause in disable_test] if disable_test else []
        self.depends_components = _clause_to_switch_or_list(depends_components)
        self.depends_filepatterns = _clause_to_switch_or_list(depends_filepatterns)

    def __hash__(self) -> int:
        return hash(self.sha)

    @property
    def sha(self) -> str:
        """
        SHA of the FolderRule instance

        :return: SHA value
        """
        sha = sha512()
        for obj in [
            self.enable,
            self.disable,
            self.disable_test,
            self.depends_components,
            self.depends_filepatterns,
        ]:
            sha.update(pickle.dumps(obj))

        return sha.hexdigest()

    def __repr__(self) -> str:
        return f'FolderRule({self.folder})'

    def _enable_build(self, target: str, config_name: str) -> bool:
        if self.enable:
            res = False
            for clause in self.enable:
                if clause.get_value(target, config_name):
                    res = True
                    break
        else:
            res = target in self.DEFAULT_BUILD_TARGETS

        if self.disable:
            for clause in self.disable:
                if clause.get_value(target, config_name):
                    res = False
                    break

        return res

    def _enable_test(
        self, target: str, default_sdkconfig_target: t.Optional[str] = None, config_name: t.Optional[str] = None
    ) -> bool:
        res = target in self.enable_build_targets(default_sdkconfig_target, config_name)

        if self.disable or self.disable_test:
            for clause in self.disable + self.disable_test:
                if clause.get_value(target, config_name or ''):
                    res = False
                    break

        return res

    def enable_build_targets(
        self, default_sdkconfig_target: t.Optional[str] = None, config_name: t.Optional[str] = None
    ) -> t.List[str]:
        res = []
        for target in ALL_TARGETS:
            if self._enable_build(target, config_name or ''):
                res.append(target)

        if default_sdkconfig_target:
            if default_sdkconfig_target not in res:
                LOGGER.debug(
                    'sdkconfig defined `CONFIG_IDF_TARGET=%s` is not enabled for folder %s. Skip building this App...',
                    default_sdkconfig_target,
                    self.folder,
                )
                return []
            else:
                LOGGER.debug(
                    'sdkconfig defined `CONFIG_IDF_TARGET=%s` overrides the supported targets for folder %s',
                    default_sdkconfig_target,
                    self.folder,
                )
                res = [default_sdkconfig_target]

        return sorted(res)

    def enable_test_targets(
        self, default_sdkconfig_target: t.Optional[str] = None, config_name: t.Optional[str] = None
    ) -> t.List[str]:
        res = []
        for target in ALL_TARGETS:
            if self._enable_test(target, default_sdkconfig_target, config_name):
                res.append(target)

        return sorted(res)


class DefaultRule(FolderRule):
    def __init__(self, folder: str) -> None:
        super().__init__(folder)


class Manifest:
    # could be reassigned later
    CHECK_MANIFEST_RULES = False

    def __init__(self, rules: t.Iterable[FolderRule], *, root_path: str = os.curdir) -> None:
        self.rules = sorted(rules, key=lambda x: x.folder)

        self._root_path = to_absolute_path(root_path)

    @classmethod
    def from_files(cls, paths: t.Iterable[str], *, root_path: str = os.curdir) -> 'Manifest':
        """
        Create a Manifest instance from multiple manifest files

        :param paths: manifest file paths
        :param root_path: root path for relative paths in manifest files
        :return: Manifest instance
        """
        # folder, defined as dict
        _known_folders: t.Dict[str, str] = dict()

        rules: t.List[FolderRule] = []
        for path in paths:
            _manifest = cls.from_file(path, root_path=root_path)

            for rule in _manifest.rules:
                if rule.folder in _known_folders:
                    msg = f'Folder "{rule.folder}" is already defined in {_known_folders[rule.folder]}'
                    if cls.CHECK_MANIFEST_RULES:
                        raise InvalidManifest(msg)
                    else:
                        LOGGER.warning(msg)

                _known_folders[rule.folder] = path

            rules.extend(_manifest.rules)

        return Manifest(rules, root_path=root_path)

    @classmethod
    def from_file(cls, path: str, *, root_path: str = os.curdir) -> 'Manifest':
        """
        Create a Manifest instance from a manifest file

        :param path: path to the manifest file
        :param root_path: root path for relative paths in manifest file
        :return: Manifest instance
        """
        manifest_dict = parse(path)

        rules: t.List[FolderRule] = []
        for folder, folder_rule in manifest_dict.items():
            # not a folder, but an anchor
            if folder.startswith('.'):
                continue

            if not os.path.isabs(folder):
                folder = os.path.join(root_path, folder)

            if not os.path.exists(folder):
                msg = f'Folder "{folder}" does not exist. Please check your manifest file {path}'
                if cls.CHECK_MANIFEST_RULES:
                    raise InvalidManifest(msg)
                else:
                    LOGGER.warning(msg)

            try:
                rules.append(FolderRule(folder, **folder_rule if folder_rule else {}))
            except InvalidIfClause as e:
                raise InvalidManifest(f'Invalid manifest file {path}: {e}')

        return Manifest(rules, root_path=root_path)

    def dump_sha_values(self, sha_filepath: str) -> None:
        """
        Dump the (relative path of the folder, SHA of the FolderRule instance) pairs
        for all rules to the file in format: ``<relative_path>:<SHA>``

        :param sha_filepath: output file path
        :return: None
        """
        with open(sha_filepath, 'w') as fw:
            for rule in self.rules:
                fw.write(f'{os.path.relpath(rule.folder, self._root_path)}:{rule.sha}\n')

    def diff_sha_with_filepath(self, sha_filepath: str, use_abspath: bool = False) -> t.Set[str]:
        """
        Compare the SHA recorded in the file with the current Manifest instance.

        :param sha_filepath: dumped SHA file path
        :param use_abspath: whether to return the absolute path of the folders
        :return: Set of folders that have different SHA values
        """
        recorded__rel_folder__sha__dict = dict()
        with open(sha_filepath) as fr:
            for line in fr:
                line = line.strip()
                if line:
                    try:
                        folder, sha_value = line.strip().rsplit(':', maxsplit=1)
                    except ValueError:
                        raise InvalidManifest(f'Invalid line in SHA file: {line}. Expected format: <folder>:<SHA>')

                    recorded__rel_folder__sha__dict[folder] = sha_value

        self__rel_folder__sha__dict = {os.path.relpath(rule.folder, self._root_path): rule.sha for rule in self.rules}

        diff_folders = set()
        if use_abspath:

            def _path(x):
                return os.path.join(self._root_path, x)
        else:

            def _path(x):
                return x

        for folder, sha_value in recorded__rel_folder__sha__dict.items():
            if folder not in self__rel_folder__sha__dict:
                diff_folders.add(_path(folder))
            elif sha_value != self__rel_folder__sha__dict[folder]:
                diff_folders.add(_path(folder))

        for folder in self__rel_folder__sha__dict:
            if folder not in recorded__rel_folder__sha__dict:
                diff_folders.add(_path(folder))

        return diff_folders

    def most_suitable_rule(self, _folder: str) -> FolderRule:
        folder = to_absolute_path(_folder)
        for rule in self.rules[::-1]:
            if os.path.commonpath([folder, rule.folder]) == rule.folder:
                return rule

        return DefaultRule(folder)

    def enable_build_targets(
        self, folder: str, default_sdkconfig_target: t.Optional[str] = None, config_name: t.Optional[str] = None
    ) -> t.List[str]:
        return self.most_suitable_rule(folder).enable_build_targets(default_sdkconfig_target, config_name)

    def enable_test_targets(
        self, folder: str, default_sdkconfig_target: t.Optional[str] = None, config_name: t.Optional[str] = None
    ) -> t.List[str]:
        return self.most_suitable_rule(folder).enable_test_targets(default_sdkconfig_target, config_name)

    def depends_components(
        self, folder: str, default_sdkconfig_target: t.Optional[str] = None, config_name: t.Optional[str] = None
    ) -> t.List[str]:
        res = self.most_suitable_rule(folder).depends_components
        if isinstance(res, list):
            return res
        return res.get_value(default_sdkconfig_target or '', config_name or '')

    def depends_filepatterns(
        self, folder: str, default_sdkconfig_target: t.Optional[str] = None, config_name: t.Optional[str] = None
    ) -> t.List[str]:
        res = self.most_suitable_rule(folder).depends_filepatterns
        if isinstance(res, list):
            return res
        return res.get_value(default_sdkconfig_target or '', config_name or '')
