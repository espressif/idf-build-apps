# SPDX-FileCopyrightText: 2023 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import os
import shutil
import subprocess

# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'idf-build-apps'
project_homepage = 'https://github.com/espressif/idf-build-apps'
copyright = '2023, Espressif Systems (Shanghai) Co., Ltd.'
author = 'Fu Hanxi'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    'sphinx.ext.autodoc',
    'sphinx_copybutton',
    'myst_parser',
    'sphinxcontrib.mermaid',
    'sphinxarg.ext',
]

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_css_files = ['theme_overrides.css']
html_logo = '_static/espressif-logo.svg'
html_static_path = ['_static']
html_theme = 'sphinx_rtd_theme'

# mermaid 10.2.0 will show syntax error
# use fixed version instead
mermaid_version = '10.6.1'

# building docs
os.environ['BUILDING_DOCS'] = '1'

# generating api docs
docs_dir = os.path.dirname(__file__)
api_dir = os.path.join(docs_dir, 'api')
if os.path.isdir(api_dir):
    shutil.rmtree(api_dir)
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
