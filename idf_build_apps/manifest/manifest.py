# SPDX-FileCopyrightText: 2022-2023 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0
import os.path
import typing as t
from pathlib import (
    Path,
)

import yaml

from .. import (
    LOGGER,
)
from ..constants import (
    ALL_TARGETS,
)
from .if_parser import (
    BOOL_EXPR,
)


class InvalidManifestError(ValueError):
    """Invalid manifest file"""


class IfClause:
    def __init__(self, stmt, temporary=False, reason=None):  # type: (str, bool, str | None) -> None
        self.stmt = BOOL_EXPR.parseString(stmt)[0]  # type: BoolExpr
        self.temporary = temporary
        self.reason = reason

        if self.temporary is True and not self.reason:
            raise InvalidManifestError('"reason" must be set when "temporary: true"')

    def get_value(self, target, config_name):  # type: (str, str) -> any
        return self.stmt.get_value(target, config_name)


class FolderRule:
    def __init__(
        self,
        folder,  # type: Path
        enable=None,  # type: list[dict[str, str]] | None
        disable=None,  # type: list[dict[str, str]] | None
        disable_test=None,  # type: list[dict[str, str]] | None
        depends_components=None,  # type: list[str] | None
        depends_filepatterns=None,  # type: list[str] | None
    ):  # type: (...) -> None
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

    def __hash__(self):
        return hash(self.folder)

    def __repr__(self):
        return f'FolderRule({self.folder})'

    def _enable_build(self, target, config_name):  # type: (str, str) -> bool
        from .. import (
            CONFIG,
        )

        if self.enable:
            res = False
            for clause in self.enable:
                if clause.get_value(target, config_name):
                    res = True
                    break
        else:
            res = target in CONFIG.default_build_targets

        if self.disable:
            for clause in self.disable:
                if clause.get_value(target, config_name):
                    res = False
                    break

        return res

    def _enable_test(
        self, target, default_sdkconfig_target=None, config_name=None
    ):  # type: (str, str | None, str | None) -> bool
        res = target in self.enable_build_targets(default_sdkconfig_target, config_name)

        if self.disable or self.disable_test:
            for clause in self.disable + self.disable_test:
                if clause.get_value(target, config_name):
                    res = False
                    break

        return res

    def enable_build_targets(
        self, default_sdkconfig_target=None, config_name=None
    ):  # type: (str | None, str | None) -> list[str]
        res = []
        for target in ALL_TARGETS:
            if self._enable_build(target, config_name):
                res.append(target)

        if default_sdkconfig_target and res != [default_sdkconfig_target]:
            res = [default_sdkconfig_target]

        LOGGER.debug('FUCK: %s', res)

        return sorted(res)

    def enable_test_targets(
        self, default_sdkconfig_target=None, config_name=None
    ):  # type: (str | None, str | None) -> list[str]
        res = []
        for target in ALL_TARGETS:
            if self._enable_test(target, default_sdkconfig_target, config_name):
                res.append(target)

        return sorted(res)


class DefaultRule(FolderRule):
    def __init__(self, folder):  # type: (Path) -> None
        super().__init__(folder)


class Manifest:
    def __init__(
        self,
        rules: t.Iterable[FolderRule],
    ) -> None:
        self.rules = sorted(rules, key=lambda x: x.folder)

    @classmethod
    def from_file(cls, path):  # type: (str) -> 'Manifest'
        from .. import (
            CONFIG,
        )

        with open(path) as f:
            manifest_dict = yaml.safe_load(f) or {}

        rules = []  # type: list[FolderRule]
        for folder, folder_rule in manifest_dict.items():
            if os.path.isabs(folder):
                folder = Path(folder)
            else:
                folder = Path(CONFIG.manifest_rootpath, folder)

            rules.append(FolderRule(folder, **folder_rule if folder_rule else {}))

        return Manifest(rules)

    def _most_suitable_rule(self, _folder):  # type: (str) -> FolderRule
        folder = Path(_folder).resolve()
        for rule in self.rules[::-1]:
            if rule.folder == folder or rule.folder in folder.parents:
                return rule

        return DefaultRule(folder)

    def enable_build_targets(
        self, folder, default_sdkconfig_target=None, config_name=None
    ):  # type: (str, str | None, str | None) -> list[str]
        return self._most_suitable_rule(folder).enable_build_targets(default_sdkconfig_target, config_name)

    def enable_test_targets(
        self, folder, default_sdkconfig_target=None, config_name=None
    ):  # type: (str, str | None, str | None) -> list[str]
        return self._most_suitable_rule(folder).enable_test_targets(default_sdkconfig_target, config_name)

    def depends_components(self, folder):  # type: (str) -> list[str]
        return self._most_suitable_rule(folder).depends_components

    def depends_filepatterns(self, folder):  # type: (str) -> list[str]
        return self._most_suitable_rule(folder).depends_filepatterns
