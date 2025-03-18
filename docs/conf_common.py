# SPDX-FileCopyrightText: 2023-2025 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import os
import shutil
import subprocess

# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html
from datetime import datetime

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'idf-build-apps'
project_homepage = 'https://github.com/espressif/idf-build-apps'
copyright = f'2023-{datetime.now().year}, Espressif Systems (Shanghai) Co., Ltd.'  # noqa: A001
author = 'Fu Hanxi'
languages = ['en']
version = '2.x'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    'sphinx.ext.autodoc',
    'sphinx_copybutton',
    'myst_parser',
    'sphinxcontrib.mermaid',
    'sphinxarg.ext',
    'sphinx_tabs.tabs',
]

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_css_files = ['theme_overrides.css']
html_logo = '../_static/espressif-logo.svg'
html_static_path = ['../_static']
html_theme = 'sphinx_rtd_theme'

# mermaid 10.2.0 will show syntax error
# use fixed version instead
mermaid_version = '10.6.1'

autodoc_default_options = {
    'members': True,
    'member-order': 'bysource',
    'show-inheritance': True,
    'exclude-members': 'model_computed_fields,model_config,model_fields,model_post_init',
}


def generate_api_docs(language):
    from idf_build_apps.args import (
        BuildArguments,
        FindArguments,
        add_args_to_obj_doc_as_params,
    )
    from idf_build_apps.main import build_apps, find_apps

    docs_dir = os.path.dirname(__file__)
    api_dir = os.path.join(docs_dir, language, 'references', 'api')
    if os.path.isdir(api_dir):
        shutil.rmtree(api_dir)

    # --- MOCK DOCSTRINGS By Arguments ---
    add_args_to_obj_doc_as_params(FindArguments)
    add_args_to_obj_doc_as_params(BuildArguments)
    add_args_to_obj_doc_as_params(FindArguments, find_apps)
    add_args_to_obj_doc_as_params(BuildArguments, build_apps)
    # --- MOCK DOCSTRINGS FINISHED ---

    subprocess.run(
        [
            'sphinx-apidoc',
            os.path.join(docs_dir, '..', 'idf_build_apps'),
            '-f',
            '-H',
            'API Reference',
            '--no-headings',
            '-t',
            '_apidoc_templates',
            '-o',
            api_dir,
        ]
    )
