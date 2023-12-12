# Manifest File

A `.build-test-rules.yml` file is the manifest file to control whether the app will be built or tested under the rules.

One typical manifest file look like this:

```yaml
[folder]:
  enable:
    - if: [if clause]
      temporary: true  # optional, default to false. `reason` is required if `temporary` is true
      reason: [your reason]  # optional
    - ...
  disable:
    - if: [if clause]
    - ...
  disable_test:
    - if: [if clause]
    - ...
```

## `if` Clauses

### Operands

- Capitalized Words
  - Variables defined in `IDF_PATH/components/soc/[TARGET]/include/soc/*_caps.h` or in `IDF_PATH/components/esp_rom/[TARGET]/*_caps.h`. e.g., `SOC_WIFI_SUPPORTED`, `ESP_ROM_HAS_SPI_FLASH`
  - `IDF_TARGET`
  - `IDF_VERSION` (IDF_VERSION_MAJOR.IDF_VERSION_MINOR.IDF_VERSION_PATCH. e.g., 5.2.0. Will convert to Version object to do a version comparison instead of a string comparison)
  - `IDF_VERSION_MAJOR`
  - `IDF_VERSION_MINOR`
  - `IDF_VERSION_PATCH`
  - `INCLUDE_DEFAULT` (The default value of officially supported targets is 1, otherwise is 0)
  - `CONFIG_NAME` (config name defined in [](project:#config-rules))
  - environment variables, default to `0` if not set
- String, must be double-quoted. e.g., `"esp32"`, `"12345"`
- Integer, support decimal and hex. e.g., `1`, `0xAB`
- List of strings or integers, or both types at the same time. e.g., `["esp32", 1]`

### Operators

- `==`, `!=`, `>`, `>=`, `<`, `<=`
- `and`, `or`
- `in`, `not in` with list
- parentheses

### Limitations

All operators are binary operators. For more than two operands, you may use the nested parentheses trick. For example:

- `A == 1 or (B == 2 and C in [1,2,3])`
- `(A == 1 and B == 2) or (C not in ["3", "4", 5])`

## Enable/Disable Rules

By default, we enable build and test for all supported targets. In other words, if an app supports all supported targets, it does not need to be added in a manifest file. The manifest files are files that set the violation rules for apps.

Three rules (disable rules are calculated after the `enable` rule):
- `enable`: run CI build/test jobs for targets that match any of the specified conditions only
- `disable`: will not run CI build/test jobs for targets that match any of the specified conditions
- `disable_test`: will not run CI test jobs for targets that match any of the specified conditions

Each key is a folder. The rule will recursively apply to all apps inside.

### Overrides Rules

If one sub folder is in a special case, you can overwrite the rules for this folder by adding another entry for this folder itself. Each folder's rules are standalone, and will not inherit its parent's rules. (YAML inheritance is too complicated for reading)

For example, in the following code block, only `disable` rule exists in `examples/foo/bar`. It's unaware of its parent's `enable` rule.

```yaml
examples/foo:
  enable:
    - if: IDF_TARGET == "esp32"

examples/foo/bar:
  disable:
    - if: IDF_TARGET == "esp32s2"
```

## Practical Example

Here's a practical example:

```yaml
examples/foo:
  enable:
    - if IDF_TARGET in ["esp32", 1, 2, 3]
    - if IDF_TARGET not in ["4", "5", 6]
  # should be run under all targets!

examples/bluetooth:
  disable:  # disable both build and tests jobs
    - if: SOC_BT_SUPPORTED != 1
    # reason is optional if there's no `temporary: true`
  disable_test:
    - if: IDF_TARGET == "esp32"
      temporary: true
      reason: lack of ci runners  # required when `temporary: true`

examples/bluetooth/test_foo:
  # each folder's settings are standalone
  disable:
    - if: IDF_TARGET == "esp32s2"
      temporary: true
      reason: no idea
  # unlike examples/bluetooth, the apps under this folder would not be build nor test for "no idea" under target esp32s2

examples/get-started/hello_world:
  enable:
    - if: IDF_TARGET == "linux"
      reason: this one only supports linux!

examples/get-started/blink:
  enable:
    - if: INCLUDE_DEFAULT == 1 or IDF_TARGET == "linux"
      reason: This one supports all supported targets and linux
```

## Building Apps Only on Related Changes

In large projects or monorepos, it is often desirable to only run builds and tests which are somehow related to the changes in a pull request.

idf-build-apps supports this by checking whether a particular app has been modified, or depends on modified components or modified files. This check is based on the knowledge of two things: the list of components/files the app depends on, and the list of components/app which are modified in the pull request.

### Specify the List of Modified Files and Components

To enable this feature, you need to pass the list of modified files or modified components to idf-build-apps using the following CLI options:

- `--modified-files`
- `--modified-components`

For example, if the project uses Git, you can obtain the list of files modified in a branch or a pull request by calling

```shell
git diff --name-only ${pr_branch_head} $(git merge-base ${pr_branch_head} main)
```

where `pr_branch_head` is the branch of the pull request, and `main` is the default branch.

### Specifying the app dependencies

idf-build-apps uses the following rules to determine whether to build an app or not:

1. The app is built if any files in the app itself are modified (.md files are excluded)
2. If `depends_components` or `depends_filepatterns` are specified in the manifest file, idf-build-apps matches `--modified-components` and `--modified-files` against these two entries. If any of the modified components are in the `depends_components` list or any of the modified files are matched by `depends_filepatterns`, the app is built.
3. If `depends_components` or `depends_filepatterns` are not specified in the manifest files, idf-build-apps determines the list of components the app depends on using `BUILD_COMPONENTS` property in IDF build system. For the given app, this property contains the list of all the components included into the build. idf-build-apps runs `idf.py reconfigure` to determine the value of this property for the app. If any of the modified components are present in the `BUILD_COMPONENTS` list, the app is built.

For example, this is an app `example/foo`, which depends on `comp1`, `comp2`, `comp3` and all files under `common_header_files`:

```yaml
examples/foo:
  depends_components:
    - comp1
    - comp2
    - comp3
  depends_filepatterns:
    - "common_header_files/**/*"
```

This app will be built with the following CLI options:

- `--modified-files examples/foo/main/foo.c`
- `--modified-components comp1`
- `--modified-components comp2;comp4 --modified-files /tmp/foo.h`
- `--modified-files common_header_files/foo.h`
- `--modified-components comp4 --modified-files common_header_files/foo.h`

This app will not be built with the following CLI options:

- `--modified-files examples/foo/main/foo.md`
- `--modified-components bar`

### Handle Low-level Dependencies

Low-level dependencies, are components or files that are used by many others. For example, component `freertos` provides the operating system support for all apps, and ESP-IDF build system related cmake files are also used by all apps. When these items are modified, we definitely need to build and test all the apps.

To disable the build-apps-only-on-related-changes feature, you can use the CLI option `--ignore-app-dependencies-filepatterns`. Once any of the modified files matches the specified patterns, the special rules will be disabled. All apps will be built, no exceptions.
