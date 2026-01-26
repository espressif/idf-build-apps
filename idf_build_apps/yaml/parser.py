# SPDX-FileCopyrightText: 2024-2026 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import typing as t

import yaml

from ..utils import PathLike


def parse_postfixes(manifest_dict: t.Dict):
    for folder, folder_rule in manifest_dict.items():
        if folder.startswith('.'):
            continue

        if not folder_rule:
            continue

        updated_folder: t.Dict = {}
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
                if isinstance(obj, t.Dict):
                    if 'if' in obj:
                        if_dict_obj.append(obj)
                    else:
                        other_dict_obj.append(obj)
                else:
                    str_obj.add(obj)

            for obj in folder_rule[key]:
                if isinstance(obj, t.Dict):
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


def flatten_common_components(manifest_dict: t.Dict):
    """
    Flattens nested lists under `depends_components` into a single list of strings.
    """

    for folder, folder_rule in manifest_dict.items():
        if not isinstance(folder_rule, t.Dict):
            continue

        depends = folder_rule.get('depends_components')
        if not isinstance(depends, t.List):
            continue

        flattened: t.List[str] = []
        for item in depends:
            if not item:
                continue
            if isinstance(item, t.List):
                flattened.extend(map(str, item))
            else:
                flattened.append(item)

        folder_rule['depends_components'] = flattened


def parse(path: PathLike, *, common_components: t.Optional[t.Sequence[str]] = None) -> t.Dict:
    common_components_yaml = (
        '.common_components: &common_components\n' + '\n'.join(f'  - {component}' for component in common_components)
        if common_components
        else '.common_components: &common_components\n  null'
    )

    with open(path, encoding='utf-8') as f:
        user_yaml = f.read()

    manifest_dict = yaml.safe_load(f'{common_components_yaml}\n{user_yaml}') or {}

    flatten_common_components(manifest_dict)
    parse_postfixes(manifest_dict)
    return manifest_dict
