# Changelog

All notable changes to this project will be documented in this file.

## v2.0.1 (2024-01-15)

### Fix

- wrongly skipped the build when `depends_filepatterns` matched but no component modified

## v2.0.0 (2024-01-11)

### Feat

- check if the folders listed in the manifest rules exist or not
- record build status in `App` instance
- support build with `make`
- support `--junitxml` option to generate junitxml report for `build`
- add `AppDeserializer` for differentiating `CMakeApp` and `MakeApp` while deserializing
- add param `check_app_dependencies` in `build_apps` function
- add param `include_skipped_apps` in `find_apps` function
- `find_apps` support custom app class for param `build_system`
- record should_be_built reason when checking app dependencies
- support override sdkconfig CLI Options `--override-sdkconfig-items` and `--override-sdkconfig-files`
- support custom `_pre_build`, `_post_build` in App instances
- add `json_to_app` method with support custom classes
- support `init_from_another` function in App instances

### Fix

- prioritize special rules defined in manifest files
- manifest folder rule starts with a `.` will be skipped checking existence
- log format more visible, from `BUILD_STAGE|` to `[BUILD_STAGE]`
- `app.size_json_path` always returns None for linux target apps
- `app.build_path` returns full path when `build_dir` is a full path, returns relative path otherwise. Before this change, it always returns full path.
- skip build while `find_apps` if `modified_components` is an empty list
- improve error message when env var `IDF_PATH` not set
- correct the search sdkconfig path function
- Turn `app.build()` arguments to kwargs

### Changes

- improve logging output. Differentiate print and logging better. print only when calling this tool via the CLI, not when using as a library

### Perf

- refactor `pathlib` calls to `os.path`, to speed up the function calls

### BREAKING CHANGES

2.x introduces a lot of breaking changes. For a detailed migration guide, please refer to our [Migration From 1.x to 2.x Guide](https://github.com/espressif/idf-build-apps/blob/main/docs/migration/1.x_to_2.x.md)

Here are the breaking changes:

- make `find_apps`, `build_apps`, keyword-only for most of the params
- migrate `App` class to pydantic model
- update dependencies and do code upgrade to python 3.7
- correct `find_apps`, `build_apps` function params. These files would be generated under the build directory.
  - `build_log_path` -> `build_log_filename`
  - `size_json_path` -> `size_json_filename`
- differentiate `None` or empty list better while checking, now these params are accepting semicolon-separated list, instead of space-separated list.
  - `--modified-components`
  - `--modified-files`
  - `--ignore-app-dependencies-filepatterns`
- make `App` init function keyword-only for most of the params
- remove `LOGGER` from `idf_build_apps`, use `logging.getLogger('idf_build_apps')` instead
- rename `build_job.py` to `build_apps_args.py`, `BuildAppJob` to `BuildAppsArgs`

## v1.1.4 (2023-12-29)

### Fix

- stop modifying yaml dict shared by yaml anchors

## v1.1.3 (2023-11-13)

### Fix

- pyyaml dependency for python version older than 3.5
- stop recursively copy when work dir in app dir

## v1.1.2 (2023-08-16)

### Feat

- improve logging when manifest file is invalid
- skip running "idf.py reconfigure" when modified components is empty

## v1.1.1 (2023-08-02)

### Fix

- ignore idf_size.py error

## v1.1.0 (2023-07-21)

### Feat

- support esp_rom caps as keywords in the manifest file

## v1.0.4 (2023-07-20)

### Fix

- stop overriding supported targets with sdkconfig file defined one for disabled app

## v1.0.3 (2023-07-19)

### Fix

- correct final reports with skipped apps and failed built apps
- skip while collecting only when both depend components and files unmatched

## v1.0.2 (2023-07-05)

### Feat

- support placeholder "@v"
- Support keyword `IDF_VERSION` in the if statement

### Fix

- non-ascii character
- build failed with warnings even without passing `--check-warnings`

## v1.0.1 (2023-06-12)

### Fixed

- glob patterns are matched recursively

## v1.0.0 (2023-05-25)

### Added

- Support keyword `depends_filepatterns` in the manifest file
- Support expanding environment variables in the manifest files

### BREAKING CHANGES

- Attributes Renamed
  - `App.requires_components` renamed to `App.depends_components`
  - `FolderRule.requires_components` renamed to `FolderRule.depends_components`
- Functions Renamed
  - `Manifest.requires_components()` renamed to `Manifest.depends_components()`
- Signatures Changed
  - `App.build()`
  - `App.is_modified()`
  - `find_apps()`
  - `build_apps()`
- CLI Options Renamed
  - `--depends-on-components` renamed to `--modified-components`
  - `--depends-on-files` renamed to `--modified-files`
  - `--ignore-components-dependencies-file-patterns` renamed to `--ignore-app-dependencies-filepatterns`
- Removed the deprecated CLI call methods, now these options only support space-separated list
  - `--exclude`
  - `--config`
  - `--manifest-file`
  - `--ignore-warning-str`
  - `--default-build-targets`

## v0.6.1 (2023-05-10)

### Fixed

- Add missing dependency `pyyaml`. It's wrongly removed in 0.6.0.

## v0.6.0 (2023-05-08) (yanked)

### Added

- Support configuration file with
  - `tool.idf-build-apps` section under `pyproject.toml` file
  - `.idf_build_apps.toml` file
- Improve help message, include default value, config name, and config type
- Improve help message, add DeprecationWarning to change the CLI call method from "specify multiple times" to "space-separated list" for the following CLI options. (will be removed in 1.0.0)
  - `--exclude`
  - `--config`
  - `--manifest-file`
  - `--ignore-warning-str`
- Support placeholder `@p` for parallel index
- Support expand placeholders for CLI options `--collect-app-info` and `--collect-size-info`
- Support new keywords `CONFIG_NAME` in the manifest file

### Fixed

- Fix earlier python version pathlib does not support member function `expanduser` issue
- Remove unused dependency `pyyaml`

### Refactored

- Move `utils.setup_logging()` to `log.setup_logging()`
- Make CLI option `--default-build-targets` from comma-separated list to space-separated list (comma-separated list support will be removed in 1.0.0)

## v0.5.2 (2023-04-07)

### Fixed

- Remove empty expanded sdkconfig files folder after build
- Split up expanded sdkconfig files folder for different build

## v0.5.1 (2023-04-06)

### Fixed

- Build with expanded sdkconfig file would respect the target-specific one under the original path

## v0.5.0 (2023-03-29)

### Added

- Add an executable script `idf-build-apps`. Now this tool could be run via `idf-build-apps build ...` instead of `python -m idf_build_apps build ...`
- Support specify `-DSDKCONFIG_DEFAULTS` for `idf.py build`
  - via CLI option `--sdkconfig-defaults`
  - via environment variable `SDKCONFIG_DEFAULTS`

### Fixed

- CLI option `-t`, `--target` is required, improve the error message

## v0.4.1 (2023-03-15)

### Fixed

- Stop writing `app_info` and `size_info` if the build got skipped
- `IDF_VERSION_MAJOR`, `IDF_VERSION_MINOR`, `IDF_VERSION_PATCH` now are integers
- Skip exclude files while removing build directory if files not exist
- Use log level `INFO` for ignored warnings
- Can't use `and` in if clauses

## v0.4.0 (2023-03-09)

This is the last version to support ESP-IDF v4.1 since it's EOL on Feb. 24th, 2023.

### Added

- Support new keywords `IDF_VERSION_MAJOR`, `IDF_VERSION_MINOR`, `IDF_VERSION_PATCH` in the manifest file
- Support colored output by default in UNIX-like systems
  - Add `--no-color` CLI option
- Support ignore check component dependencies based on changed files and specified file patterns
  - Add `--ignore-component-dependencies-file-patterns` CLI option
  - Add `--depends-on-files` CLI option

### Fixed

- Improve the readability of the generated logs

## v0.3.2 (2023-03-08)

### Fixed

- `idf.py reconfigure` without setting `IDF_TARGET`
- wrong log level on "Loading manifest file: ...". Set from `INFO` to `DEBUG`
- wrong log level on "Building app \[ID\]: ...". Set from `DEBUG` to `INFO`

## v0.3.1 (2023-02-20)

### Fixed

- Relative path defined in the manifest files depend on the current work path

  Added `manifest_rootpath` argument in `find_apps()`. Will use this value instead as the root folder for calculating absolute path

## v0.3.0 (2023-01-10)

### Added

- `find_apps`, `build_apps` support `--depends-on-components`, will only find or build apps that require specified components
- manifest file support `requires_components`

### Fixed

-  Wrong `App.verified_targets` when `CONFIG_IDF_TARGET` set in app's `sdkconfig.defaults` file

## v0.2.1 (2022-09-02)

### Fixed

- Fix `--format json` incompatible issue for IDF branches earlier than 5.0
- Fix type annotations incompatible issue for python versions earlier than 3.7
- Fix f-string incompatible issue for python versions earlier than 3.7
- Fix unpack dictionary ending comma syntax error for python 3.4

## v0.2.0 (2022-08-31)

### Added

- Use `--format json` instead of `--json` with `idf_size.py`
