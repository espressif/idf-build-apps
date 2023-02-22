# Find and Build Apps

## Find Apps

### Basics

```shell
cd examples
python -m idf_build_apps find -p . --recursive --target esp32
```

The output would be:

```text
(cmake) App ./test1, target esp32, sdkconfig (default), build in /tmp/test/examples/test1/build
(cmake) App ./test2, target esp32, sdkconfig (default), build in /tmp/test/examples/test2/build
```

By default, `idf-build-apps` would build the default app.

### Advanced

You may also notice that there are two sdkconfig files in app `test1`, we could also find apps for each sdkconfig files.

```shell
python -m idf_build_apps find -p . --recursive --target esp32 --config "sdkconfig.ci.*="
```

The output would be:

```text
(cmake) App ./test1, target esp32, sdkconfig sdkconfig.ci.bar, build in /tmp/test/examples/test1/build
(cmake) App ./test1, target esp32, sdkconfig sdkconfig.ci.foo, build in /tmp/test/examples/test1/build
(cmake) App ./test2, target esp32, sdkconfig (default), build in /tmp/test/examples/test2/build
```

Here we're using a wildcard symbol `*` to indicate that we want to build one app for each sdkconfig file that matches the wildcard pattern.

### Build Directory

Here you may notice that all the build directories are `build` by default. We also defined a few placeholders to let you change the build directories.

- `@t`: would be replaced by the target chip type
- `@w`: would be replaced by the wildcard, usually the sdkconfig
- `@n`: would be replaced by the app name
- `@f`: would be replaced by the escaped app path (replaced "/" to "_")
- `@i`: would be replaced by the build index

For example, if you want to set the build directory to `build_<target>_<wildcard>`

```shell
python -m idf_build_apps find -p . --recursive --target esp32 --config "sdkconfig.ci.*=" --build-dir build_@t_@w
```

The output would be:

```text
(cmake) App ./test1, target esp32, sdkconfig sdkconfig.ci.bar, build in /tmp/test/examples/test1/build_esp32_bar
(cmake) App ./test1, target esp32, sdkconfig sdkconfig.ci.foo, build in /tmp/test/examples/test1/build_esp32_foo
(cmake) App ./test2, target esp32, sdkconfig (default), build in /tmp/test/examples/test2/build_esp32
```

You may also set an absolute path as the build directory. `/tmp/build/<app_name>.<target>.<wildcard>`

```shell
python -m idf_build_apps find -p . --recursive --target esp32 --config "sdkconfig.ci.*=" --build-dir /tmp/build/@n_@t_@w
```

The output would be:

```text
(cmake) App ./test1, target esp32, sdkconfig sdkconfig.ci.bar, build in /tmp/build/test1_esp32_bar
(cmake) App ./test1, target esp32, sdkconfig sdkconfig.ci.foo, build in /tmp/build/test1_esp32_foo
(cmake) App ./test2, target esp32, sdkconfig (default), build in /tmp/build/test2_esp32
```

## Build Apps

Almost all CLI options that `find` supported are also supported in `build` command. You may call `python -m idf_build_apps find -h` or `python -m idf_build_apps build -h` for all possible CLI options.

### Useful Tips

#### Check Build Warnings

You may use `--check-warnings` to enable this check. Also we provide `--ignore-warnings-str` and `--ignore-warnings-file` to let you bypass some false alarm.

#### Dry Run

It's useful to call `--dry-run` with verbose mode `-vv` to know the whole build process better in advance.

For example:

```shell
python -m idf_build_apps build -p . --recursive --target esp32 --dry-run -vv --config "sdkconfig.ci.*="
```

The output would be:

```text
2023-02-22 11:16:25 DEBUG Looking for cmake apps in . recursively
2023-02-22 11:16:25 DEBUG Entering .
2023-02-22 11:16:25 DEBUG Skipping. . is not an app
2023-02-22 11:16:25 DEBUG Entering ./test1
2023-02-22 11:16:25 DEBUG Found cmake app: ./test1, sdkconfig sdkconfig.ci.bar, config name "bar"
2023-02-22 11:16:25 DEBUG Found cmake app: ./test1, sdkconfig sdkconfig.ci.foo, config name "foo"
2023-02-22 11:16:25 DEBUG Stop iteration sub dirs of ./test1 since it has apps
2023-02-22 11:16:25 DEBUG Entering ./test2
2023-02-22 11:16:25 DEBUG Found cmake app: ./test2, default sdkconfig, config name ""
2023-02-22 11:16:25 DEBUG Stop iteration sub dirs of ./test2 since it has apps
2023-02-22 11:16:25 INFO Found 3 apps in total
2023-02-22 11:16:25 INFO Total 3 apps. running build for app 1-3
2023-02-22 11:16:25 INFO Building the following apps:
2023-02-22 11:16:25 INFO   (cmake) App ./test1, target esp32, sdkconfig sdkconfig.ci.bar, build in /tmp/test/examples/test1/build (preserve: True)
2023-02-22 11:16:25 INFO   (cmake) App ./test1, target esp32, sdkconfig sdkconfig.ci.foo, build in /tmp/test/examples/test1/build (preserve: True)
2023-02-22 11:16:25 INFO   (cmake) App ./test2, target esp32, sdkconfig (default), build in /tmp/test/examples/test2/build (preserve: True)
2023-02-22 11:16:25 DEBUG => Building app 1: (cmake) App ./test1, target esp32, sdkconfig sdkconfig.ci.bar, build in /tmp/test/examples/test1/build
2023-02-22 11:16:25 DEBUG Build directory /tmp/test/examples/test1/build exists, removing
2023-02-22 11:16:25 DEBUG Removing sdkconfig file: ./test1/sdkconfig
2023-02-22 11:16:25 DEBUG Creating sdkconfig file: ./test1/sdkconfig
2023-02-22 11:16:25 DEBUG Considering sdkconfig ./test1/sdkconfig.defaults
2023-02-22 11:16:25 DEBUG Considering sdkconfig ./test1/sdkconfig.defaults.esp32
2023-02-22 11:16:25 DEBUG Considering sdkconfig ./test1/sdkconfig.ci.bar
2023-02-22 11:16:25 DEBUG Appending sdkconfig.ci.bar to sdkconfig
2023-02-22 11:16:25 INFO Running /tmp/test/.espressif/python_env/idf5.1_py3.11_env/bin/python /tmp/test/esp/esp-idf/tools/idf.py -B /tmp/test/examples/test1/build -C ./test1 -DIDF_TARGET=esp32 build
2023-02-22 11:16:25 DEBUG Skipping... (dry run)
2023-02-22 11:16:25 DEBUG => Building app 2: (cmake) App ./test1, target esp32, sdkconfig sdkconfig.ci.foo, build in /tmp/test/examples/test1/build
2023-02-22 11:16:25 DEBUG Build directory /tmp/test/examples/test1/build exists, removing
2023-02-22 11:16:25 DEBUG Removing sdkconfig file: ./test1/sdkconfig
2023-02-22 11:16:25 DEBUG Creating sdkconfig file: ./test1/sdkconfig
2023-02-22 11:16:25 DEBUG Considering sdkconfig ./test1/sdkconfig.defaults
2023-02-22 11:16:25 DEBUG Considering sdkconfig ./test1/sdkconfig.defaults.esp32
2023-02-22 11:16:25 DEBUG Considering sdkconfig ./test1/sdkconfig.ci.foo
2023-02-22 11:16:25 DEBUG Appending sdkconfig.ci.foo to sdkconfig
2023-02-22 11:16:25 INFO Running /tmp/test/.espressif/python_env/idf5.1_py3.11_env/bin/python /tmp/test/esp/esp-idf/tools/idf.py -B /tmp/test/examples/test1/build -C ./test1 -DIDF_TARGET=esp32 build
2023-02-22 11:16:25 DEBUG Skipping... (dry run)
2023-02-22 11:16:25 DEBUG => Building app 3: (cmake) App ./test2, target esp32, sdkconfig (default), build in /tmp/test/examples/test2/build
2023-02-22 11:16:25 DEBUG Creating sdkconfig file: ./test2/sdkconfig
2023-02-22 11:16:25 DEBUG Considering sdkconfig ./test2/sdkconfig.defaults
2023-02-22 11:16:25 DEBUG Considering sdkconfig ./test2/sdkconfig.defaults.esp32
2023-02-22 11:16:25 INFO Running /tmp/test/.espressif/python_env/idf5.1_py3.11_env/bin/python /tmp/test/esp/esp-idf/tools/idf.py -B /tmp/test/examples/test2/build -C ./test2 -DIDF_TARGET=esp32 build
2023-02-22 11:16:25 DEBUG Skipping... (dry run)
```
