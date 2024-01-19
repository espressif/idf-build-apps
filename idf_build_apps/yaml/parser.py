# SPDX-FileCopyrightText: 2024 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import typing as t

import yaml


def parse_postfixes(manifest_dict: t.Dict):
    for folder, folder_rule in manifest_dict.items():
        if folder.startswith('.'):
            continue
        updated_folder: t.Dict = {}
        sorted_keys = sorted(folder_rule)
        for key in sorted_keys:
            if not key.endswith(('+', '-')):
                updated_folder[key] = folder_rule[key]
                continue

            operation = key[-1]

            dict_obj = []
            str_obj = set()
            for obj in updated_folder[key[:-1]]:
                if isinstance(obj, t.Dict):
                    dict_obj.append(obj)
                else:
                    str_obj.add(obj)

            for obj in folder_rule[key]:
                if isinstance(obj, t.Dict):
                    dict_obj = [obj_j for obj_j in dict_obj if obj['if'] != obj_j['if']]
                    if operation == '+':
                        dict_obj.append(obj)
                else:
                    str_obj.add(obj) if operation == '+' else str_obj.remove(obj)

            updated_folder[key[:-1]] = dict_obj + sorted(str_obj)

        manifest_dict[folder] = updated_folder


def parse(path: str) -> t.Dict:
    with open(path) as f:
        manifest_dict = yaml.safe_load(f) or {}
    parse_postfixes(manifest_dict)
    return manifest_dict
