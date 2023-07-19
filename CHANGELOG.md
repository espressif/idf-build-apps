# Changelog

All notable changes to this project will be documented in this file.

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
