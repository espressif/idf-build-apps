# SPDX-FileCopyrightText: 2023 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import os
import re
import typing as t


class SessionArgs:
    workdir: str = os.getcwd()
    override_sdkconfig_items: t.Dict[str, t.Any] = {}
    override_sdkconfig_file_path: t.Optional[str] = None

    def set(self, parsed_args, *, workdir=None):
        if workdir:
            self.workdir = workdir
        self._setup_override_sdkconfig(parsed_args)

    def clean(self):
        self.override_sdkconfig_items = {}
        self.override_sdkconfig_file_path = None

    def _setup_override_sdkconfig(self, args):
        override_sdkconfig_items = self._get_override_sdkconfig_items(
            args.override_sdkconfig_items.split(',') if args.override_sdkconfig_items else ()
        )
        override_sdkconfig_files_items = self._get_override_sdkconfig_files_items(
            args.override_sdkconfig_files.split(',') if args.override_sdkconfig_files else ()
        )

        override_sdkconfig_files_items.update(override_sdkconfig_items)
        self.override_sdkconfig_items = override_sdkconfig_files_items

        override_sdkconfig_merged_file = self._create_override_sdkconfig_merged_file(self.override_sdkconfig_items)
        self.override_sdkconfig_file_path = override_sdkconfig_merged_file

    def _get_override_sdkconfig_files_items(self, override_sdkconfig_files: t.Tuple[str]) -> t.Dict:
        dct = {}
        for f in override_sdkconfig_files:
            if not os.path.isabs(f):
                f = os.path.join(self.workdir, f)
            if not os.path.isfile(f):
                continue
            with open(f) as fr:
                for line in fr:
                    m = re.compile(r"^([^=]+)=\"?([^\"\n]*)\"?\n*$").match(line)
                    if not m:
                        continue
                    dct[m.group(1)] = m.group(2)
        return dct

    def _get_override_sdkconfig_items(self, override_sdkconfig_items: t.Tuple[str]) -> t.Dict:
        dct = {}
        for line in override_sdkconfig_items:
            m = re.compile(r"^([^=]+)=\"?([^\"\n]*)\"?\n*$").match(line)
            if m:
                dct[m.group(1)] = m.group(2)
        return dct

    def _create_override_sdkconfig_merged_file(self, override_sdkconfig_merged_items) -> t.Optional[str]:
        if not override_sdkconfig_merged_items:
            return None
        f_path = os.path.join(self.workdir, 'override-result.sdkconfig')
        with open(f_path, 'w+') as f:
            for key, value in override_sdkconfig_merged_items.items():
                f.write(f'{key}={value}\n')
        return f_path
