# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Fixed

- Stop writing `app_info` and `size_info` if the build got skipped
- `IDF_VERSION_MAJOR`, `IDF_VERSION_MINOR`, `IDF_VERSION_PATCH` now are integers
- Skip exclude files while removing build directory if files not exist
- Can't use `and` expression

## [0.4.0]

This is the last version to support ESP-IDF v4.1 since it's EOL on Feb. 24th, 2023.

### Added

- Support new keywords `IDF_VERSION_MAJOR`, `IDF_VERSION_MINOR`, `IDF_VERSION_PATCH`
- Support colored output by default in UNIX-like systems
  - Add `--no-color` CLI option
- Support ignore check component dependencies based on changed files and specified file patterns
  - Add `--ignore-component-dependencies-file-patterns` CLI option
  - Add `--depends-on-files` CLI option

### Fixed

- Improve the readability of the generated logs

## [0.3.2]

### Fixed

- `idf.py reconfigure` without setting `IDF_TARGET`
- wrong log level on "Loading manifest file: ...". Set from `INFO` to `DEBUG`
- wrong log level on "Building app \[ID\]: ...". Set from `DEBUG` to `INFO`

## [0.3.1]

### Fixed

- Ralative path defined in the manifest files depend on the current work path

  Added `manifest_rootpath` argument in `find_apps()`. Will use this value instead as the root folder for calculating absolute path

## [0.3.0]

### Added

- `find_apps`, `build_apps` support `--depends-on-components`, will only find or build apps that require specified components
- manifest file support `requires_components`

### Fixed

-  Wrong `App.verified_targets` when `CONFIG_IDF_TARGET` set in app's `sdkconfig.defaults` file

## [0.2.1]

### Fixed

- Fix `--format json` incompatible issue for IDF branches earlier than 5.0
- Fix type annotations incompatible issue for python versions earlier than 3.7
- Fix f-string incompatible issue for python versions earlier than 3.7
- Fix unpack dictionary ending comma syntax error for python 3.4

## [0.2.0]

### Added

- Use `--format json` instead of `--json` with `idf_size.py`
