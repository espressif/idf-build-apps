# SPDX-FileCopyrightText: 2024-2025 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import os
from typing import Optional

from .utils import AutocompleteActivationError


def append_to_file(file_path: str, content: str) -> None:
    """Add commands to shell configuration file

    :param file_path: path to shell configurations file
    :param content: commands to add
    """
    if os.path.exists(file_path):
        with open(file_path) as file:
            if content.strip() in file.read():
                print(f'Autocompletion already set up in {file_path}')
                return
    with open(file_path, 'a') as file:
        file.write(f'\n# Begin added by idf-build-apps \n{content} \n# End added by idf-build-apps')
    print(f'Autocompletion added to {file_path}')


def activate_completions(shell_type: Optional[str]) -> None:
    """Activates autocompletion for supported shells.

    :raises AutocompleteActivationError: if the $SHELL env variable is empty, or if the detected shell is unsupported.
    """
    supported_shells = ['bash', 'zsh', 'fish']

    if shell_type == 'auto':
        shell_type = os.path.basename(os.environ.get('SHELL', ''))

    if not shell_type:
        raise AutocompleteActivationError('$SHELL is empty. Please provide your shell type with the `--shell` option')

    if shell_type not in supported_shells:
        raise AutocompleteActivationError('Unsupported shell. Autocompletion is supported for bash, zsh and fish.')

    if shell_type == 'bash':
        completion_command = 'eval "$(register-python-argcomplete idf-build-apps)"'
    elif shell_type == 'zsh':
        completion_command = (
            'autoload -U bashcompinit && bashcompinit && eval "$(register-python-argcomplete idf-build-apps)"'
        )
    elif shell_type == 'fish':
        completion_command = 'register-python-argcomplete --shell fish idf-build-apps | source'

    rc_file = {'bash': '~/.bashrc', 'zsh': '~/.zshrc', 'fish': '~/.config/fish/completions/idf-build-apps.fish'}

    shell_rc = os.path.expanduser(rc_file[shell_type])
    append_to_file(shell_rc, completion_command)
