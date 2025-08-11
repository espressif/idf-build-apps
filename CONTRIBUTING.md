# Contributions Guide

Hi! We're glad that you're interested in contributing to `idf-build-apps`. This document would guide you through the process of setting up the development environment, running tests, and building documentation.

## Supported ESP-IDF Versions

Here's a table shows the supported ESP-IDF versions and the corresponding Python versions.

| ESP-IDF Version | ESP-IDF Version EOL | ESP-IDF Minimum Python Version | idf-build-apps Releases |
|-----------------|---------------------|--------------------------------|-------------------------|
| 5.1             | 2025.12.30          | 3.7                            | 2.x                     |
| 5.2             | 2026.08.16          | 3.8                            | 2.x                     |
| 5.3             | 2027.01.25          | 3.8                            | 2.x                     |
| 5.4             | 2027.07.05          | 3.8                            | 2.x                     |
| 5.5             | 2028.01.21          | 3.9                            | 2.x                     |
| 6.0 (master)    | N/A                 | 3.10                           | 3.x WIP                 |

`idf-build-apps` is following the semantic versioning. The major version of `idf-build-apps` is the same as the ESP-IDF version it supports. For example, `idf-build-apps` 1.x supports ESP-IDF 4.x, and `idf-build-apps` 2.x supports ESP-IDF 5.x.

In order to compatible to all 5.x ESP-IDF versions, please don't forget to keep the code compatible with python 3.7, even it's end of life on 2023-06-05.

Besides, pydantic dropped 3.7 support since 2.6.0. Don't rely on pydantic 2.6.0+ since we're still supporting python 3.7.

## Setup the Dev Environment

1. Create virtual environment

    ```shell
    python -m venv venv
    ```

2. Activate the virtual environment

    ```shell
    . ./venv/bin/activate
    ```

3. Install [flit][flit]

    We use [flit][flit] to build the package and install the dependencies.

    ```shell
    pip install flit
    ```

4. Install all dependencies

    All dependencies would be installed, and our package `idf-build-apps` would be installed with editable mode.

    ```shell
    flit install -s
    ```

## Run Testing

We use [pytest][pytest] for testing.

```shell
pytest
```

## Build Documentation

We use [sphinx][sphinx] and [autodoc][autodoc] for generating documentation and API references. Besides, we treat warnings as errors while building the documentation. Please fix them before your commits got merged.

```shell
cd docs/en && make html
```

For documentation preview, you may use any browser you prefer. The executable has to be searchable in `PATH`. For example we're using firefox here.

```shell
firefox _build/html/index.html
```

[flit]: https://flit.pypa.io/en/stable/index.html
[pytest]: https://docs.pytest.org/en/stable/contents.html
[sphinx]: https://www.sphinx-doc.org/en/master/
[autodoc]: https://www.sphinx-doc.org/en/master/usage/quickstart.html#autodoc
