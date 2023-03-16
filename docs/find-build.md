# Find and Build Apps

This chapter mainly explains what's running behind the two main functions, `find` and `build`.

## Find Apps

Finding apps is a process that collects all the buildable applications from the specified paths.

To explain the process better, we would use the folder `/tmp/test/examples` as an example. The folder structure looks like this:

```text
/tmp/test/examples
├── test-1
│   ├── CMakeLists.txt
│   ├── main
│   │   ├── CMakeLists.txt
│   │   └── test-1.c
│   ├── sdkconfig.ci.bar
│   ├── sdkconfig.ci.foo
│   ├── sdkconfig.defaults
│   └── sdkconfig.defaults.esp32
└── test-2
    ├── CMakeLists.txt
    └── main
        ├── CMakeLists.txt
        └── test-2.c
```

### Basics

The basic command to find all the buildable apps under `/tmp/test/examples` recursively with target `esp32` is:

```shell
cd /tmp/test/examples
idf-build-apps find -p . --recursive --target esp32
```

The output would be:

```text
(cmake) App ./test-1, target esp32, sdkconfig (default), build in /tmp/test/examples/test-1/build
(cmake) App ./test-2, target esp32, sdkconfig (default), build in /tmp/test/examples/test-2/build
```

By default, when you're building an [ESP-IDF][esp-idf] project, it would generate a default [sdkconfig][sdkconfig] file. `idf-build-apps` would use this configuration file to build the default app.

The default sdkconfig file for test-1 would be generated in this order:

```{mermaid}
flowchart TB
    kconfig(Kconfig default values)
    sdkconfig(sdkconfig.defaults)
    sdkconfig_target(sdkconfig.defaults.TARGET)

    kconfig -- be overriden by --> sdkconfig -- be overriden by --> sdkconfig_target

    subgraph "which would only be applied when building with the corresponding target"
    sdkconfig_target
    end
```

### Config Rules

Config rule represents the sdkconfig file pattern and the config name. The syntax is simple: `[FILE_PATTERN]=[CONFIG_NAME]`.

- `FILE_PATTERN`: Name of the sdkconfig file, optionally with a single wildcard (`*`) character.
- `CONFIG_NAME`: Name of the corresponding build configuration, or None if the value of wildcard is to be used.

For example, in project `test-1`:

```{eval-rst}

.. list-table:: Config Rules
   :widths: 15 15 55 15
   :header-rows: 1

   *  - Config Rule
      - Config Name
      - Explanation
      - Extra sdkconfig file
   *  - ``=``
      - ``default``
      - The default value of config name is ``default``
      -
   *  - ``sdkconfig.ci.foo=test``
      - ``test``
      -
      - ``sdkconfig.ci.foo``
   *  - ``sdkconfig.not_exists=test``
      - ``default``
      - The config rule doesn't match any sdkconfig file. Use the default value instead.
      -
   *  - ``sdkconfig.ci.*=``
      -  - ``foo``
         - ``bar``
      - The wildcard matches two files. Build two apps based on each sdkconfig file.
      -  - ``sdkconfig.ci.foo``
         - ``sdkconfig.ci.bar``

.. note::

   For each config rule, only one wildcard is supported.
```

### Placeholders for Work Directory and Build Directory

Here we defined two new terms of directories, work directory and build directory.

#### Work Directory

Work directory is the directory where the build actually happens. `idf-build-apps` would first copy the whole project to the work directory, then start the real build process. The benefit of specifying work directory is that you could keep your local build directory and `sdkconfig` file untouched.

By default, `idf-build-apps` would use the project directory as the work directory.

#### Build Directory

Build directory is the directory where the binary files output would be generated. If it is set to a relative path, the full path would be calculated based on the work directory. If it is a absolute path, it would override the work directory settings.

By default, `idf-build-apps` would follow what ESP-IDF does, use `build` as the build directory.

#### Placeholders

Placeholders are a set of symbols, which could be used when setting work directory and build directory. The placeholders would be replaced while building as follows:

- `@t`: Would be replaced by the target chip type.
- `@w`: Would be replaced by the wildcard if exists, otherwise would be replaced by the config name.
- `@n`: Would be replaced by the project name.
- `@f`: Would be replaced by the escaped project path (replaced "/" to "_").
- `@i`: Would be replaced by the build index. (only available in `build` command)

For example,

```shell
idf-build-apps find -p . --recursive --target esp32 --config "sdkconfig.ci.*=" --build-dir build_@t_@w
```

The output would be:

```text
(cmake) App ./test-1, target esp32, sdkconfig sdkconfig.ci.bar, build in /tmp/test/examples/test-1/build_esp32_bar
(cmake) App ./test-1, target esp32, sdkconfig sdkconfig.ci.foo, build in /tmp/test/examples/test-1/build_esp32_foo
(cmake) App ./test-2, target esp32, sdkconfig (default), build in /tmp/test/examples/test-2/build_esp32
```

Another example to set an absolute path with the wildcard symbols as the build directory:

```shell
idf-build-apps find -p . --recursive --target esp32 --config "sdkconfig.ci.*=" --build-dir /tmp/build/@n_@t_@w
```

The output would be:

```text
(cmake) App ./test-1, target esp32, sdkconfig sdkconfig.ci.bar, build in /tmp/build/test-1_esp32_bar
(cmake) App ./test-1, target esp32, sdkconfig sdkconfig.ci.foo, build in /tmp/build/test-1_esp32_foo
(cmake) App ./test-2, target esp32, sdkconfig (default), build in /tmp/build/test-2_esp32
```

## Build Apps

Building apps is a process that build all the applications that are collected by the "finding apps" process.

```{eval-rst}

.. note::

   Almost all CLI options that ``find`` supported are also supported in ``build`` command. You may call ``idf-build-apps find -h`` or ``idf-build-apps build -h`` for all possible CLI options.
```

### Tips on `build` CLI Options

#### Check Build Warnings

You may use `--check-warnings` to enable this check. If any warning is captured while the building process, the exit code would turn to a non-zero value. Besides, `idf-build-apps` provides CLI options `--ignore-warnings-str` and `--ignore-warnings-file` to let you bypass some false alarms.

#### Dry Run

It's useful to call `--dry-run` with verbose mode `-vv` to know the whole build process in detail before the build actually happens.

For example:

```shell
idf-build-apps build -p . --recursive --target esp32 --dry-run -vv --config "sdkconfig.ci.*="
```

The output would be:

```text
2023-03-08 16:26:41    DEBUG Looking for cmake apps in . recursively
2023-03-08 16:26:41    DEBUG Entering .
2023-03-08 16:26:41    DEBUG Skipping. . is not an app
2023-03-08 16:26:41    DEBUG Entering ./test-2
2023-03-08 16:26:41    DEBUG Found cmake app: ./test-2, default sdkconfig, config name ""
2023-03-08 16:26:41    DEBUG Stop iteration sub dirs of ./test-2 since it has apps
2023-03-08 16:26:41    DEBUG Entering ./test-1
2023-03-08 16:26:41    DEBUG Found cmake app: ./test-1, sdkconfig sdkconfig.ci.bar, config name "bar"
2023-03-08 16:26:41    DEBUG Found cmake app: ./test-1, sdkconfig sdkconfig.ci.foo, config name "foo"
2023-03-08 16:26:41    DEBUG Stop iteration sub dirs of ./test-1 since it has apps
2023-03-08 16:26:41     INFO Found 3 apps in total
2023-03-08 16:26:41     INFO Total 3 apps. running build for app 1-3
2023-03-08 16:26:41     INFO Building the following apps:
2023-03-08 16:26:41     INFO   (cmake) App ./test-1, target esp32, sdkconfig sdkconfig.ci.bar, build in /tmp/test/examples/test-1/build (preserve: True)
2023-03-08 16:26:41     INFO   (cmake) App ./test-1, target esp32, sdkconfig sdkconfig.ci.foo, build in /tmp/test/examples/test-1/build (preserve: True)
2023-03-08 16:26:41     INFO   (cmake) App ./test-2, target esp32, sdkconfig (default), build in /tmp/test/examples/test-2/build (preserve: True)
2023-03-08 16:26:41     INFO Building app 1: (cmake) App ./test-1, target esp32, sdkconfig sdkconfig.ci.bar, build in /tmp/test/examples/test-1/build
2023-03-08 16:26:41    DEBUG => Preparing Folders
2023-03-08 16:26:41    DEBUG => Generating sdkconfig file
2023-03-08 16:26:41    DEBUG ==> Creating sdkconfig file: ./test-1/sdkconfig
2023-03-08 16:26:41    DEBUG ==> Considering sdkconfig ./test-1/sdkconfig.defaults
2023-03-08 16:26:41    DEBUG ==> Appending sdkconfig.defaults to sdkconfig
2023-03-08 16:26:41    DEBUG ==> Considering sdkconfig ./test-1/sdkconfig.defaults.esp32
2023-03-08 16:26:41    DEBUG ==> Appending sdkconfig.defaults.esp32 to sdkconfig
2023-03-08 16:26:41    DEBUG ==> Considering sdkconfig ./test-1/sdkconfig.ci.bar
2023-03-08 16:26:41    DEBUG ==> Appending sdkconfig.ci.bar to sdkconfig
2023-03-08 16:26:41    DEBUG ==> Skipping... (dry run)
2023-03-08 16:26:41     INFO Building app 2: (cmake) App ./test-1, target esp32, sdkconfig sdkconfig.ci.foo, build in /tmp/test/examples/test-1/build
2023-03-08 16:26:41    DEBUG => Preparing Folders
2023-03-08 16:26:41    DEBUG => Generating sdkconfig file
2023-03-08 16:26:41    DEBUG ==> Creating sdkconfig file: ./test-1/sdkconfig
2023-03-08 16:26:41    DEBUG ==> Considering sdkconfig ./test-1/sdkconfig.defaults
2023-03-08 16:26:41    DEBUG ==> Appending sdkconfig.defaults to sdkconfig
2023-03-08 16:26:41    DEBUG ==> Considering sdkconfig ./test-1/sdkconfig.defaults.esp32
2023-03-08 16:26:41    DEBUG ==> Appending sdkconfig.defaults.esp32 to sdkconfig
2023-03-08 16:26:41    DEBUG ==> Considering sdkconfig ./test-1/sdkconfig.ci.foo
2023-03-08 16:26:41    DEBUG ==> Appending sdkconfig.ci.foo to sdkconfig
2023-03-08 16:26:41    DEBUG ==> Skipping... (dry run)
2023-03-08 16:26:41     INFO Building app 3: (cmake) App ./test-2, target esp32, sdkconfig (default), build in /tmp/test/examples/test-2/build
2023-03-08 16:26:41    DEBUG => Preparing Folders
2023-03-08 16:26:41    DEBUG => Generating sdkconfig file
2023-03-08 16:26:41    DEBUG ==> Creating sdkconfig file: ./test-2/sdkconfig
2023-03-08 16:26:41    DEBUG ==> Considering sdkconfig ./test-2/sdkconfig.defaults
2023-03-08 16:26:41    DEBUG ==> Considering sdkconfig ./test-2/sdkconfig.defaults.esp32
2023-03-08 16:26:41    DEBUG ==> Skipping... (dry run)
```

[esp-idf]: https://github.com/espressif/esp-idf
[sdkconfig]: https://docs.espressif.com/projects/esp-idf/en/latest/esp32/api-reference/kconfig.html
