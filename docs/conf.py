# SPDX-FileCopyrightText: 2023 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

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
]

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_css_files = ['theme_overrides.css']
html_logo = '_static/espressif-logo.svg'
html_static_path = ['_static']
html_theme = 'sphinx_rtd_theme'

# mermaid 10.0.0 change the CDN path
# temp workaround until sphinxcontrib-mermaid fixed it
mermaid_version = '9.4.0'
