# idf-build-apps

[![Documentation Status](https://readthedocs.com/projects/espressif-idf-build-apps/badge/?version=latest)](https://espressif-docs.readthedocs-hosted.com/projects/idf-build-apps/en/latest/)
[![pypi_package_version](https://img.shields.io/pypi/v/idf-build-apps)](https://pypi.org/project/idf_build_apps/)
[![supported_python_versions](https://img.shields.io/pypi/pyversions/idf-build-apps)](https://pypi.org/project/idf_build_apps/)

`idf-build-apps` is a tool that helps users find and build [ESP-IDF][esp-idf], and [ESP8266 RTOS][esp8266-rtos] projects in a large scale.

## What is an `app`?

A project using [ESP-IDF][esp-idf] SDK, or [ESP8266 RTOS][esp8266-rtos] SDK typically contains:

- Build recipe in CMake or Make and the main component with app sources
- (Optional) One or more [sdkconfig][sdkconfig] files

`app` is the abbreviation for application. An application is a set of binary files that is being built with the specified [sdkconfig][sdkconfig] and the target chip. `idf-build-apps` could build one project into a number of applications according to the matrix of these two parameters.

## Installation

```shell
pip install idf-build-apps
```

or `pipx`

```shell
pipx install idf-build-apps
```

## Basic Usage

`idf-build-apps` is a python package that could be used as a library or a CLI tool.

As a CLI tool, it contains three sub-commands.

- `find` to find the buildable applications
- `build` to build the found applications
- `completions` to activate autocompletions or print instructions for manual activation

For detailed explanation to all CLI options, you may run

```shell
idf-build-apps -h
idf-build-apps find -h
idf-build-apps build -h
idf-build-apps completions -h
```

As a library, you may check the [API documentation][api-doc] for more information. Overall it provides

- Two functions, `find_apps` and `build_apps`
- Two classes, `CMakeApp` and `MakeApp`

## Quick CLI Example

To build [ESP-IDF hello world example project][hello-world] with ESP32:

```shell
idf-build-apps build -p $IDF_PATH/examples/get-started/hello_world/ --target esp32
```

The binary files will be generated under `$IDF_PATH/examples/get-started/hello_world/build` directory.

## Documentation

For detailed information, please refer to [our documentation site][doc]!

## Contributing

Thanks for your contribution! Please refer to our [Contributing Guide](CONTRIBUTING.md)

[esp-idf]: https://github.com/espressif/esp-idf
[esp8266-rtos]: https://github.com/espressif/ESP8266_RTOS_SDK
[sdkconfig]: https://docs.espressif.com/projects/esp-idf/en/latest/esp32/api-reference/kconfig.html
[hello-world]: https://github.com/espressif/esp-idf/tree/master/examples/get-started/hello_world
[supported-targets]: https://github.com/espressif/esp-idf/tree/v5.0#esp-idf-release-and-soc-compatibility
[doc]: https://docs.espressif.com/projects/idf-build-apps/en/latest/
[api-doc]: https://docs.espressif.com/projects/idf-build-apps/en/latest/references/api/modules.html
