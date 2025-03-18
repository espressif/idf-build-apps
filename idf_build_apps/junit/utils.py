# SPDX-FileCopyrightText: 2023-2025 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import os
import platform
import re
import socket
import sys
import typing as t


def get_size(b: float) -> str:
    for unit in ['', 'K', 'M', 'G', 'T', 'P']:
        if b < 1024:
            return f'{b:.2f}{unit}B'
        b /= 1024

    return f'{b:.2f}EB'


def get_processor_name():
    if platform.processor():
        return platform.processor()

    # read from /proc/cpuinfo
    if os.path.isfile('/proc/cpuinfo'):
        try:
            with open('/proc/cpuinfo') as f:
                for line in f:
                    if 'model name' in line:
                        return re.sub('.*model name.*:', '', line, count=1).strip()
        except Exception:
            pass

    return ''


def get_sys_info() -> t.Dict[str, str]:
    info = {
        'platform': platform.system(),
        'platform-release': platform.release(),
        'architecture': platform.machine(),
        'hostname': socket.gethostname(),
        'processor': get_processor_name(),
        'cpu_count': str(os.cpu_count()) if os.cpu_count() else 'Unknown',
    }

    if sys.platform != 'win32':
        info['ram'] = get_size(os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES'))

    return info
