# SPDX-FileCopyrightText: 2022-2023 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import logging
import os
import typing as t
import warnings
from pathlib import (
    Path,
)

import yaml
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


class FolderRule:
    DEFAULT_BUILD_TARGETS = SUPPORTED_TARGETS

    def __init__(
        self,
        folder: Path,
        enable: t.Optional[t.List[t.Dict[str, t.Any]]] = None,
        disable: t.Optional[t.List[t.Dict[str, t.Any]]] = None,
        disable_test: t.Optional[t.List[t.Dict[str, t.Any]]] = None,
        depends_components: t.Optional[t.List[str]] = None,
        depends_filepatterns: t.Optional[t.List[str]] = None,
    ) -> None:
        self.folder = folder.resolve()

        for group in [enable, disable, disable_test]:
            if group:
                for d in group:
                    d['stmt'] = d['if']  # avoid keyword `if`
                    del d['if']

        self.enable = [IfClause(**clause) for clause in enable] if enable else []
        self.disable = [IfClause(**clause) for clause in disable] if disable else []
        self.disable_test = [IfClause(**clause) for clause in disable_test] if disable_test else []
        self.depends_components = depends_components or []
        self.depends_filepatterns = depends_filepatterns or []

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
    def __init__(self, folder: Path) -> None:
        super().__init__(folder)


class Manifest:
    # could be reassigned later
    ROOTPATH = Path(os.curdir)
    CHECK_MANIFEST_RULES = False

    def __init__(
        self,
        rules: t.Iterable[FolderRule],
    ) -> None:
        self.rules = sorted(rules, key=lambda x: x.folder)

    @classmethod
    def from_file(cls, path: str) -> 'Manifest':
        with open(path) as f:
            manifest_dict = yaml.safe_load(f) or {}

        rules: t.List[FolderRule] = []
        for folder, folder_rule in manifest_dict.items():
            # not a folder, but a anchor
            if folder.startswith('.'):
                continue

            if os.path.isabs(folder):
                folder = Path(folder)
            else:
                folder = Path(cls.ROOTPATH, folder)

            if not folder.exists():
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
        folder = Path(_folder).resolve()
        for rule in self.rules[::-1]:
            if rule.folder == folder or rule.folder in folder.parents:
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

    def depends_components(self, folder: str) -> t.List[str]:
        return self._most_suitable_rule(folder).depends_components

    def depends_filepatterns(self, folder: str) -> t.List[str]:
        return self._most_suitable_rule(folder).depends_filepatterns
