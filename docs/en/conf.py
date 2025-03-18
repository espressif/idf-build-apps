# SPDX-FileCopyrightText: 2024-2025 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import os
import sys

language = 'en'

sys.path.insert(0, os.path.abspath('../'))

from conf_common import *  # noqa

generate_api_docs(language)  # noqa
