# SPDX-FileCopyrightText: 2022 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path

import yaml

from .if_parser import BOOL_EXPR, BoolExpr
from ..constants import ALL_TARGETS, SUPPORTED_TARGETS


class InvalidManifestError(ValueError):
    """Invalid manifest file"""


class IfClause:
    def __init__(
        self, stmt, temporary=False, reason=None
    ):  # type: (str, bool, str | None) -> None
        self.stmt: BoolExpr = BOOL_EXPR.parseString(stmt)[0]
        self.temporary = temporary
        self.reason = reason

        if self.temporary is True and not self.reason:
            raise InvalidManifestError('"reason" must be set when "temporary: true"')

    def get_value(self, target):  # type: (str) -> any
        return self.stmt.get_value(target)


class FolderRule:
    DEFAULT_BUILD_TARGETS = SUPPORTED_TARGETS

    def __init__(
        self,
        folder,
        enable=None,
        disable=None,
        disable_test=None,
    ):  # type: (Path, list[dict[str, str]] | None, list[dict[str, str]] | None, list[dict[str, str]] | None) -> None
        self.folder = folder.resolve()

        for group in [enable, disable, disable_test]:
            if group:
                for d in group:
                    d['stmt'] = d['if']  # avoid keyword `if`
                    del d['if']

        self.enable = [IfClause(**clause) for clause in enable] if enable else []
        self.disable = [IfClause(**clause) for clause in disable] if disable else []
        self.disable_test = (
            [IfClause(**clause) for clause in disable_test] if disable_test else []
        )

        # cache attrs
        self._enable_build_targets = None
        self._enable_test_targets = None

    def __hash__(self):
        return hash(self.folder)

    def __repr__(self):
        return f'FolderRule({self.folder})'

    def _enable_build(self, target):  # type: (str) -> bool
        if self.enable:
            res = False
            for clause in self.enable:
                if clause.get_value(target):
                    res = True
                    break
        else:
            res = target in self.DEFAULT_BUILD_TARGETS

        if self.disable:
            for clause in self.disable:
                if clause.get_value(target):
                    res = False
                    break

        return res

    def _enable_test(self, target):  # type: (str) -> bool
        res = target in self.enable_build_targets

        if self.disable or self.disable_test:
            for clause in self.disable + self.disable_test:
                if clause.get_value(target):
                    res = False
                    break

        return res

    @property
    def enable_build_targets(self):
        if self._enable_build_targets is not None:
            return self._enable_build_targets

        res = []
        for target in ALL_TARGETS:
            if self._enable_build(target):
                res.append(target)

        self._enable_build_targets = sorted(res)
        return self._enable_build_targets

    @property
    def enable_test_targets(self):
        if self._enable_test_targets is not None:
            return self._enable_test_targets

        res = []
        for target in ALL_TARGETS:
            if self._enable_test(target):
                res.append(target)

        self._enable_test_targets = sorted(res)
        return self._enable_test_targets


class DefaultRule(FolderRule):
    def __init__(self, folder: Path):
        super().__init__(folder)


class Manifest:
    def __init__(self, rules):  # type: (list[FolderRule] | set[FolderRule]) -> None
        self.rules = sorted(rules, key=lambda x: x.folder)

    @staticmethod
    def from_file(path):  # type: (str) -> 'Manifest'
        with open(path) as f:
            manifest_dict = yaml.safe_load(f) or {}

        rules = []  # type: list[FolderRule]
        for folder, folder_rule in manifest_dict.items():
            folder = Path(folder)
            rules.append(
                FolderRule(
                    folder,
                    **folder_rule if folder_rule else {},
                )
            )

        return Manifest(rules)

    def _most_suitable_rule(self, _folder):  # type: (str) -> FolderRule
        folder = Path(_folder).resolve()
        for rule in self.rules[::-1]:
            if rule.folder == folder or rule.folder in folder.parents:
                return rule

        return DefaultRule(folder)

    def enable_build_targets(self, folder):  # type: (str) -> list[str]
        return self._most_suitable_rule(folder).enable_build_targets

    def enable_test_targets(self, folder):  # type: (str) -> list[str]
        return self._most_suitable_rule(folder).enable_test_targets
