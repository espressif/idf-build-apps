# Changelog

All notable changes to this project will be documented in this file.

## [0.5.1] (2023-04-06)

### Fixed

- Build with expanded sdkconfig file would respect the target-specific one under the original path

## [0.5.0] (2023-03-29)

### Added

- Add an executable script `idf-build-apps`. Now this tool could be run via `idf-build-apps build ...` instead of `python -m idf_build_apps build ...`
- Support specify `-DSDKCONFIG_DEFAULTS` for `idf.py build`
  - via CLI option `--sdkconfig-defaults`
  - via environment variable `SDKCONFIG_DEFAULTS`

### Fixed

- CLI option `-t`, `--target` is required, improve the error message

## [0.4.1] (2023-03-15)

### Fixed

- Stop writing `app_info` and `size_info` if the build got skipped
- `IDF_VERSION_MAJOR`, `IDF_VERSION_MINOR`, `IDF_VERSION_PATCH` now are integers
- Skip exclude files while removing build directory if files not exist
- Use log level `INFO` for ignored warnings
- Can't use `and` in if clauses

## [0.4.0] (2023-03-09)

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

## [0.3.2] (2023-03-08)

### Fixed

- `idf.py reconfigure` without setting `IDF_TARGET`
- wrong log level on "Loading manifest file: ...". Set from `INFO` to `DEBUG`
- wrong log level on "Building app \[ID\]: ...". Set from `DEBUG` to `INFO`

## [0.3.1] (2023-02-20)

### Fixed

- Ralative path defined in the manifest files depend on the current work path

  Added `manifest_rootpath` argument in `find_apps()`. Will use this value instead as the root folder for calculating absolute path

## [0.3.0] (2023-01-10)

### Added

- `find_apps`, `build_apps` support `--depends-on-components`, will only find or build apps that require specified components
- manifest file support `requires_components`

### Fixed

-  Wrong `App.verified_targets` when `CONFIG_IDF_TARGET` set in app's `sdkconfig.defaults` file

## [0.2.1] (2022-09-02)

### Fixed

- Fix `--format json` incompatible issue for IDF branches earlier than 5.0
- Fix type annotations incompatible issue for python versions earlier than 3.7
- Fix f-string incompatible issue for python versions earlier than 3.7
- Fix unpack dictionary ending comma syntax error for python 3.4

## [0.2.0] (2022-08-31)

### Added

- Use `--format json` instead of `--json` with `idf_size.py`
