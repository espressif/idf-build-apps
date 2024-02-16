# SPDX-FileCopyrightText: 2022-2024 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import logging
import os
import typing as t
import warnings

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
        return hash(self.folder)

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
    ROOTPATH = os.curdir
    CHECK_MANIFEST_RULES = False

    def __init__(
        self,
        rules: t.Iterable[FolderRule],
    ) -> None:
        self.rules = sorted(rules, key=lambda x: x.folder)

    @classmethod
    def from_files(cls, paths: t.List[str]) -> 'Manifest':
        # folder, defined_at dict
        _known_folders: t.Dict[str, str] = dict()

        rules: t.List[FolderRule] = []
        for path in paths:
            _manifest = cls.from_file(path)

            for rule in _manifest.rules:
                if rule.folder in _known_folders:
                    msg = f'Folder "{rule.folder}" is already defined in {_known_folders[rule.folder]}'
                    if cls.CHECK_MANIFEST_RULES:
                        raise InvalidManifest(msg)
                    else:
                        warnings.warn(msg)

                _known_folders[rule.folder] = path

            rules.extend(_manifest.rules)

        return Manifest(rules)

    @classmethod
    def from_file(cls, path: str) -> 'Manifest':
        manifest_dict = parse(path)

        rules: t.List[FolderRule] = []
        for folder, folder_rule in manifest_dict.items():
            # not a folder, but a anchor
            if folder.startswith('.'):
                continue

            if not os.path.isabs(folder):
                folder = os.path.join(cls.ROOTPATH, folder)

            if not os.path.exists(folder):
                msg = f'Folder "{folder}" does not exist. Please check your manifest file {path}'
                if cls.CHECK_MANIFEST_RULES:
                    raise InvalidManifest(msg)
                else:
                    warnings.warn(msg)

            try:
                rules.append(FolderRule(folder, **folder_rule if folder_rule else {}))
            except InvalidIfClause as e:
                raise InvalidManifest(f'Invalid manifest file {path}: {e}')

        return Manifest(rules)

    def _most_suitable_rule(self, _folder: str) -> FolderRule:
        folder = os.path.abspath(_folder)
        for rule in self.rules[::-1]:
            if os.path.commonpath([folder, rule.folder]) == rule.folder:
                return rule

        return DefaultRule(folder)

    def enable_build_targets(
        self, folder: str, default_sdkconfig_target: t.Optional[str] = None, config_name: t.Optional[str] = None
    ) -> t.List[str]:
        return self._most_suitable_rule(folder).enable_build_targets(default_sdkconfig_target, config_name)

    def enable_test_targets(
        self, folder: str, default_sdkconfig_target: t.Optional[str] = None, config_name: t.Optional[str] = None
    ) -> t.List[str]:
        return self._most_suitable_rule(folder).enable_test_targets(default_sdkconfig_target, config_name)

    def depends_components(
        self, folder: str, default_sdkconfig_target: t.Optional[str] = None, config_name: t.Optional[str] = None
    ) -> t.List[str]:
        res = self._most_suitable_rule(folder).depends_components
        if isinstance(res, list):
            return res
        return res.get_value(default_sdkconfig_target or '', config_name or '')

    def depends_filepatterns(
        self, folder: str, default_sdkconfig_target: t.Optional[str] = None, config_name: t.Optional[str] = None
    ) -> t.List[str]:
        res = self._most_suitable_rule(folder).depends_filepatterns
        if isinstance(res, list):
            return res
        return res.get_value(default_sdkconfig_target or '', config_name or '')
