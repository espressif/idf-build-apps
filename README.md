# idf-build-apps

## Getting Started

### Installation

```shell
pip install idf-build-apps
```

### Quick Example

To build the apps for all targets of [ESP-IDF hello world example](https://github.com/espressif/esp-idf/tree/master/examples/get-started/hello_world)

```shell
python -m idf_build_apps build -p $IDF_PATH/examples/get-started/hello_world/ --target all --build-dir build_@t
```

would build

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

For detailed information, please refer to our documentation site.

## Contributing

Thanks for your contribution! Please refer to our [Contributing Guide](CONTRIBUTING.md)
