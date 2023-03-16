# idf-build-apps

[![Documentation Status](https://readthedocs.com/projects/espressif-idf-build-apps/badge/?version=latest)](https://espressif-docs.readthedocs-hosted.com/projects/idf-build-apps/en/latest/)
[![pypi_package_version](https://img.shields.io/pypi/v/idf-build-apps)](https://pypi.org/project/idf_build_apps/)
[![supported_python_versions](https://img.shields.io/pypi/pyversions/idf-build-apps)](https://pypi.org/project/idf_build_apps/)

`idf-build-apps` is a tool that helps users find and build [ESP-IDF][esp-idf] projects faster.

## What is an `app`?

An [ESP-IDF][esp-idf] project would typically contain:

- Build recipe in CMake and the main component with app sources
- (Optional) One or more [sdkconfig][sdkconfig] files

`app` is the abbreviation for application. An application is the binary that is being built with the specified [sdkconfig][sdkconfig] and the target chip. `idf-build-apps` could build one project into a number of applications.

## Installation

```shell
pip install idf-build-apps
```

or `pipx`

```shell
pipx install idf-build-apps
```

## Basic Usage

`idf-build-apps` is a callable python package, and an executable script with the same name would also be installed. It contains two sub-commands.

- `find` to find the buildable applications
- `build` to build the found applications

For detailed explanation to all CLI options, you may run

```shell
idf-build-apps -h
idf-build-apps find -h
idf-build-apps build -h
```

## Quick Example

To build the applications for all targets of the [ESP-IDF hello world example project][hello-world] under ESP-IDF v5.0:

```shell
idf-build-apps build -p $IDF_PATH/examples/get-started/hello_world/ --target all --build-dir build_@t
```

It would get the default [supported targets][supported-targets] from your IDF version, build the [hello world project][hello-world] with all targets and the default `sdkconfig` file.

Partial build log:

```text
2023-02-22 12:14:58 INFO Found 5 apps in total
2023-02-22 12:14:58 INFO Total 5 apps. running build for app 1-5
2023-02-22 12:14:58 INFO Building the following apps:
2023-02-22 12:14:58 INFO   (cmake) App /tmp/test/esp/esp-idf/examples/get-started/hello_world/, target esp32, sdkconfig (default), build in /tmp/test/esp/esp-idf/examples/get-started/hello_world/build_esp32 (preserve: True)
2023-02-22 12:14:58 INFO   (cmake) App /tmp/test/esp/esp-idf/examples/get-started/hello_world/, target esp32c2, sdkconfig (default), build in /tmp/test/esp/esp-idf/examples/get-started/hello_world/build_esp32c2 (preserve: True)
2023-02-22 12:14:58 INFO   (cmake) App /tmp/test/esp/esp-idf/examples/get-started/hello_world/, target esp32c3, sdkconfig (default), build in /tmp/test/esp/esp-idf/examples/get-started/hello_world/build_esp32c3 (preserve: True)
2023-02-22 12:14:58 INFO   (cmake) App /tmp/test/esp/esp-idf/examples/get-started/hello_world/, target esp32s2, sdkconfig (default), build in /tmp/test/esp/esp-idf/examples/get-started/hello_world/build_esp32s2 (preserve: True)
2023-02-22 12:14:58 INFO   (cmake) App /tmp/test/esp/esp-idf/examples/get-started/hello_world/, target esp32s3, sdkconfig (default), build in /tmp/test/esp/esp-idf/examples/get-started/hello_world/build_esp32s3 (preserve: True)
```

For detailed information, please refer to [our documentation site][doc]!

## Contributing

Thanks for your contribution! Please refer to our [Contributing Guide](CONTRIBUTING.md)

[esp-idf]: https://github.com/espressif/esp-idf
[sdkconfig]: https://docs.espressif.com/projects/esp-idf/en/latest/esp32/api-reference/kconfig.html
[hello-world]: https://github.com/espressif/esp-idf/tree/master/examples/get-started/hello_world
[supported-targets]: https://github.com/espressif/esp-idf/tree/v5.0#esp-idf-release-and-soc-compatibility
[doc]: https://docs.espressif.com/projects/idf-build-apps/en/latest/
