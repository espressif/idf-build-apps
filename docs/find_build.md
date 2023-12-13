# Find and Build Apps

This chapter mainly explains what's running behind the two main functions, `find_apps` and `build_apps`.

## Find Apps

Finding apps is a process that collects all the buildable applications from the specified paths.

To explain the process better, let's go through an example with two projects `test-1` and `test-2`, under folder `/tmp/test/examples`. The folder structure looks like this:

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

The basic command to find all the buildable apps under `/tmp/test/examples` recursively with target `esp32` is:

```shell
cd /tmp/test/examples
idf-build-apps find -p . --recursive --target esp32
```

The output would be:

```text
(cmake) App ./test-1, target esp32, sdkconfig (default), build in ./test-1/build
(cmake) App ./test-2, target esp32, sdkconfig (default), build in ./test-2/build
```

### `sdkconfig` Files

To customize ESP-IDF projects configurations, developers can run a terminal-based tool `idf.py menuconfig` interactively, or create `sdkconfig.defaults` files. For detailed documentation, please refer to [ESP-IDF Project Configuration Guide][sdkconfig].

Usually in CI, calling `idf.py menuconfig` interactively is not possible. We use a set of `sdkconfig.defaults` files instead. Each line of the `sdkconfig` files is a key-value pair, representing a configuration item. For example, `CONFIG_IDF_TARGET_ESP32=y`.

The ESP-IDF build system automatically creates the`sdkconfig` file, which collects all the configuration items, then start the compilation. The build system will first read the settings from the `sdkconfig.defaults` files, then populate the rest of the settings based on these values, and the default values set in the `Kconfig` files.

The `sdkconfig` file is generated in this order:

```{mermaid}
flowchart TB
    sdkconfig_defaults(sdkconfig.defaults)
    sdkconfig_defaults_target(sdkconfig.defaults.TARGET)

    kconfig(Other Kconfig items)

    sdkconfig_file(`sdkconfig` file)

    subgraph pre-set [pre-set Kconfig items]
        sdkconfig_defaults -- be overriden by --> sdkconfig_defaults_target

        subgraph "only apply when building with the target"
            sdkconfig_defaults_target
        end
    end

    pre-set -- configure together with the default value of each Kconfig item --> kconfig -- generates --> sdkconfig_file
```

#### Overriding Kconfig Items

`idf-build-apps` provides CLI options available to globally override kconfig items. Each option is a comma-separated list.

- `--override-sdkconfig-items`
- `--override-sdkconfig-files`

Each item is a Kconfig item, as we mentioned earlier. Each file contains multiple lines of Kconfig items, to simplify the CLI usage.

If you use multiple override options together, the `sdkconfig` file is generated in this order:

```{mermaid}
flowchart TB
    sdkconfig_defaults(sdkconfig.defaults)
    sdkconfig_defaults_target(sdkconfig.defaults.TARGET)

    kconfig(Other Kconfig items)

    sdkconfig_file(`sdkconfig` file)

    override_sdkconfig_items(items defined in --override-sdkconfig-items)
    override_sdkconfig_files(items defined in --override-sdkconfig-files)

    subgraph pre-set [pre-set Kconfig items]
        direction TB

        sdkconfig_defaults -- be overriden by --> sdkconfig_defaults_target

        subgraph "only apply when building with the target"
            sdkconfig_defaults_target
        end

        sdkconfig_defaults_target -- be overriden by --> override_sdkconfig_files -- be overriden by --> override_sdkconfig_items
    end

    pre-set -- configure together with the default value of each Kconfig item --> kconfig -- generates --> sdkconfig_file
```

The sequence in each CLI option also matters. The later one would override the previous one. For example,

```shell
idf-build-apps find -p test-1 --target esp32 --override-sdkconfig-items CONFIG_A=4,CONFIG_A=5
```

Will consider `CONFIG_A=5`, but running with:

```shell
idf-build-apps find -p test-1 --target esp32 --override-sdkconfig-items CONFIG_A=5,CONFIG_A=4
```

Will consider `CONFIG_A=4`.

(config-rules)=
### Config Rules

In CI, we may want to build the same project with different configurations, to increase our test coverage. `idf-build-apps` provides a way to do this by using config rules.

Config rule represents a relationship that matches the sdkconfig file pattern and the config name. The syntax is simple: `[SDKCONFIG_FILEPATTERN]=[CONFIG_NAME]`.

- `SDKCONFIG_FILEPATTERN`: could be a file name, to match a single `sdkconfig` file, or with one wildcard (`*`) character, to match multiple `sdkconfig` files.
- `CONFIG_NAME`: Name of the corresponding build configuration. or skip setting this value if the value of wildcard is to be used.

For example, in project `test-1`, the config rules and the corresponding sdkconfig files could be:

```{eval-rst}

.. list-table:: Config Rules
   :widths: 15 15 55 15
   :header-rows: 1

   *  - Config Rule
      - Config Name
      - Explanation
      - Matched sdkconfig file
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
```

To build the project with the config rules, we could run:

```shell
idf-build-apps find -p . --recursive --target esp32 --config [CONFIG_RULE]
```

For example,

```shell
idf-build-apps find -p test-1 --target esp32 --config "sdkconfig.ci.*="
```

The output is:

```text
(cmake) App test-1, target esp32, sdkconfig sdkconfig.ci.bar, build in test-1/build
(cmake) App test-1, target esp32, sdkconfig sdkconfig.ci.foo, build in test-1/build
```

You may also use multiple `config rules` options together:

```shell
idf-build-apps find -p test-1 --target esp32 --config "sdkconfig.ci.*=" "sdkconfig.defaults=default"
```

The output is:

```text
(cmake) App test-1, target esp32, sdkconfig sdkconfig.ci.bar, build in test-1/build
(cmake) App test-1, target esp32, sdkconfig sdkconfig.ci.foo, build in test-1/build
(cmake) App test-1, target esp32, sdkconfig sdkconfig.defaults, build in test-1/build
```

```{note}
For each `SDKCONFIG_FILEPATTERN`, only one wildcard is supported.
```

### Placeholders for Work Directory and Build Directory

As native ESP-IDF does, `idf-build-apps` builds projects in-place, within the project directory, and generates the binaries under `build` directory. `idf-build-apps` also provides a way to customize the work directory and build directory.

#### Work Directory

Work directory is the directory where the build actually happens. `idf-build-apps` would first copy the whole project to the work directory, then start the real build process. The benefit of specifying work directory is that you could keep your local build directory and `sdkconfig` file untouched.

By default, `idf-build-apps` would use the project directory as the work directory.

#### Build Directory

Build directory is the directory where the binary files output would be generated. If it is set to a relative path, the full path would be calculated based on the work directory. If it is an absolute path, it would override the work directory settings.

#### Placeholders

To make the work directory and build directory more flexible, `idf-build-apps` provides a way to use placeholders in the directory path.

Placeholders are a set of symbols, which could be used when setting work directory and build directory. The placeholders would be replaced while building as follows:

- `@t`: Would be replaced by the target chip type.
- `@w`: Would be replaced by the wildcard if exists, otherwise would be replaced by the config name.
- `@n`: Would be replaced by the project name.
- `@f`: Would be replaced by the escaped project path (replaced "/" to "_").
- `@i`: Would be replaced by the build index. (only available in `build` command)
- `@p`: Would be replaced by the parallel build index. (default to `1`, only available in `build` command)

For example,

```shell
idf-build-apps find -p . --recursive --target esp32 --config "sdkconfig.ci.*=" --build-dir build_@t_@w
```

The output would be:

```text
(cmake) App ./test-1, target esp32, sdkconfig sdkconfig.ci.bar, build in ./test-1/build_esp32_bar
(cmake) App ./test-1, target esp32, sdkconfig sdkconfig.ci.foo, build in ./test-1/build_esp32_foo
(cmake) App ./test-2, target esp32, sdkconfig (default), build in ./test-2/build_esp32
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

### Output in Text File

For `find` command, you may use `--output <file>` to output the result to a text file. Each line of the text file represents an app, which is a JSON string that could be deserialized to an `App` object.

You may reuse the file with python code:

```python
from idf_build_apps import AppDeserializer

with open("output.txt", "r") as f:
    for line in f:
        app = AppDeserializer.from_json(line)
```

## Build Apps

Building apps is a process that build all the applications that are collected by the "find" process.

```{note}
Almost all CLI options that ``find`` supported are also supported in ``build`` command. You may call ``idf-build-apps find -h`` or ``idf-build-apps build -h`` to get a full list of all possible CLI options.
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
2023-12-12 13:36:03    DEBUG Looking for CMakeApp apps in . recursively with target esp32
2023-12-12 13:36:03    DEBUG Entering .
2023-12-12 13:36:03    DEBUG Skipping. . is not an app
2023-12-12 13:36:03    DEBUG Entering ./test-1
2023-12-12 13:36:03    DEBUG Use sdkconfig file ./test-1/sdkconfig.defaults
2023-12-12 13:36:03    DEBUG Use sdkconfig file ./test-1/sdkconfig.ci.bar
2023-12-12 13:36:03    DEBUG Found app: (cmake) App ./test-1, target esp32, sdkconfig sdkconfig.ci.bar, build in ./test-1/build
2023-12-12 13:36:03    DEBUG
2023-12-12 13:36:03    DEBUG Use sdkconfig file ./test-1/sdkconfig.defaults
2023-12-12 13:36:03    DEBUG Use sdkconfig file ./test-1/sdkconfig.ci.foo
2023-12-12 13:36:03    DEBUG Found app: (cmake) App ./test-1, target esp32, sdkconfig sdkconfig.ci.foo, build in ./test-1/build
2023-12-12 13:36:03    DEBUG
2023-12-12 13:36:03    DEBUG => Stop iteration sub dirs of ./test-1 since it has apps
2023-12-12 13:36:03    DEBUG Entering ./test-2
2023-12-12 13:36:03    DEBUG sdkconfig file ./test-2/sdkconfig.defaults not exists, skipping...
2023-12-12 13:36:03    DEBUG Found app: (cmake) App ./test-2, target esp32, sdkconfig (default), build in ./test-2/build
2023-12-12 13:36:03    DEBUG
2023-12-12 13:36:03    DEBUG => Stop iteration sub dirs of ./test-2 since it has apps
2023-12-12 13:36:03     INFO Found 3 apps in total
2023-12-12 13:36:03     INFO Total 3 apps. running build for app 1-3
2023-12-12 13:36:03     INFO (1/3) Building app: (cmake) App ./test-1, target esp32, sdkconfig sdkconfig.ci.bar, build in ./test-1/build
2023-12-12 13:36:03     INFO skipped (dry run)
2023-12-12 13:36:03     INFO
2023-12-12 13:36:03     INFO (2/3) Building app: (cmake) App ./test-1, target esp32, sdkconfig sdkconfig.ci.foo, build in ./test-1/build
2023-12-12 13:36:03     INFO skipped (dry run)
2023-12-12 13:36:03     INFO
2023-12-12 13:36:03     INFO (3/3) Building app: (cmake) App ./test-2, target esp32, sdkconfig (default), build in ./test-2/build
2023-12-12 13:36:03     INFO skipped (dry run)
2023-12-12 13:36:03     INFO
Skipped building the following apps:
  (cmake) App ./test-1, target esp32, sdkconfig sdkconfig.ci.bar, build in ./test-1/build, skipped in 0.000176s: dry run
  (cmake) App ./test-1, target esp32, sdkconfig sdkconfig.ci.foo, build in ./test-1/build, skipped in 7.4e-05s: dry run
  (cmake) App ./test-2, target esp32, sdkconfig (default), build in ./test-2/build, skipped in 7.2e-05s: dry run
```

## Logging

All commands provided by `idf-build-apps` are using the same logger `idf_build_apps`. By default the logger level is `WARNING`. You may use `-v` to increase the logger level to `INFO`, and `-vv` to increase the logger level to `DEBUG`. You may use `idf_build_apps.setup_logging` to setup the logger level programmatically.

To fully customize the logger, you may get the logger of `idf_build_apps` with:

```python
import logging

logging.getLogger("idf_build_apps")
```

[esp-idf]: https://github.com/espressif/esp-idf
[sdkconfig]: https://docs.espressif.com/projects/esp-idf/en/latest/esp32/api-reference/kconfig.html
