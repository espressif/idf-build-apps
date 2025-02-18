# SPDX-FileCopyrightText: 2022-2025 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import enum
import os

import esp_bool_parser

IDF_PATH = esp_bool_parser.IDF_PATH
IDF_PY = os.path.join(IDF_PATH, 'tools', 'idf.py')
IDF_SIZE_PY = os.path.join(IDF_PATH, 'tools', 'idf_size.py')

PROJECT_DESCRIPTION_JSON = 'project_description.json'
DEFAULT_SDKCONFIG = 'sdkconfig.defaults'

SUPPORTED_TARGETS = esp_bool_parser.SUPPORTED_TARGETS
PREVIEW_TARGETS = esp_bool_parser.PREVIEW_TARGETS
ALL_TARGETS = esp_bool_parser.ALL_TARGETS
IDF_VERSION_MAJOR = esp_bool_parser.IDF_VERSION_MAJOR
IDF_VERSION_MINOR = esp_bool_parser.IDF_VERSION_MINOR
IDF_VERSION_PATCH = esp_bool_parser.IDF_VERSION_PATCH
IDF_VERSION = esp_bool_parser.IDF_VERSION


class BuildStatus(str, enum.Enum):
    UNKNOWN = 'unknown'
    DISABLED = 'disabled'
    SKIPPED = 'skipped'
    SHOULD_BE_BUILT = 'should be built'
    FAILED = 'build failed'
    SUCCESS = 'build success'


completion_instructions = """
With the `--activate` option, detect your shell type and add the appropriate commands to your shell's config file
so that it runs on startup. You will likely have to restart.
or re-login for the autocompletion to start working.

You can also specify your shell using the `--shell` option.

If you do not want automatic modification of your shell configuration file
You can manually add the commands provided below to activate autocompletion.
or run them in your current terminal session for one-time activation.

Once again, you will likely have to restart
or re-login for the autocompletion to start working.

bash:
    eval "$(register-python-argcomplete idf-build-apps)"

zsh:
    To activate completions in zsh, first make sure compinit is marked for
    autoload and run autoload:

    autoload -U compinit
    compinit

    Afterwards you can enable completions for idf-build-apps:

    eval "$(register-python-argcomplete idf-build-apps)"

fish:
    # Not required to be in the config file, only run once
    register-python-argcomplete --shell fish idf-build-apps >~/.config/fish/completions/idf-build-apps.fish
"""
IDF_BUILD_APPS_TOML_FN = '.idf_build_apps.toml'
