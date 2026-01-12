# SPDX-FileCopyrightText: 2024-2026 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import re
import typing as t

import yaml

from ..utils import PathLike


def parse_postfixes(manifest_dict: dict):
    for folder, folder_rule in manifest_dict.items():
        if folder.startswith('.'):
            continue

        if not folder_rule:
            continue

        updated_folder: dict = {}
        sorted_keys = sorted(folder_rule)
        for key in sorted_keys:
            if not key.endswith(('+', '-')):
                updated_folder[key] = folder_rule[key]
                continue

            operation = key[-1]

            if_dict_obj = []
            other_dict_obj = []
            str_obj = set()
            for obj in updated_folder[key[:-1]]:
                if isinstance(obj, dict):
                    if 'if' in obj:
                        if_dict_obj.append(obj)
                    else:
                        other_dict_obj.append(obj)
                else:
                    str_obj.add(obj)

            for obj in folder_rule[key]:
                if isinstance(obj, dict):
                    _l = obj['if']
                    if isinstance(_l, str):
                        _l = _l.replace(' ', '')

                    new_dict_obj = []
                    for obj_j in if_dict_obj:
                        _r = obj_j['if']
                        if isinstance(_r, str):
                            _r = _r.replace(' ', '')
                        if _l != _r:
                            new_dict_obj.append(obj_j)
                    if_dict_obj = new_dict_obj

                    if operation == '+':
                        if_dict_obj.append(obj)
                else:
                    str_obj.add(obj) if operation == '+' else str_obj.remove(obj)

            updated_folder[key[:-1]] = if_dict_obj + other_dict_obj + sorted(str_obj)

        manifest_dict[folder] = updated_folder


def replace_common_components(data: str, root_components: t.Sequence[str]):
    if not root_components:
        return data

    def _replace_with_indent(match, replacement: str) -> str:
        indent = match.group(1)
        if not replacement:
            return ''
        return '\n'.join(indent + line for line in replacement.splitlines())

    def _format_yaml_string_list(items: t.Sequence[str]) -> str:
        items = [str(i) for i in items]
        return '\n'.join(f"- '{item}'" for item in items)

    data = re.sub(
        r'^([ \t]*)\{\{\s*root_components\s*}}',
        lambda match: _replace_with_indent(match, replacement=_format_yaml_string_list(root_components)),
        data,
        flags=re.MULTILINE,
    )
    return data


def parse(path: PathLike, *, root_components: t.Sequence[str] | None = None) -> dict:
    with open(path) as f:
        data = replace_common_components(f.read(), root_components=root_components or [])
        manifest_dict = yaml.safe_load(data) or {}

    parse_postfixes(manifest_dict)
    return manifest_dict
