# Changelog

All notable changes to this project will be documented in this file.

## v2.11.0 (2025-06-03)

### Feat

- support extra_pythonpaths injection during the runtime

## v2.10.3 (2025-06-03)

### Fix

- app.target have higher precedence than target while `find_apps`
- respect FolderRule.DEFAULT_BUILD_TARGETS while validating app

### Refactor

- move `FolderRule.DEFAULT_BUILD_TARGET` into contextvar

## v2.10.2 (2025-05-22)

### Perf

- `most_suitable_rule` stop searching till reached root dir
- pre-compute rules folder, reduced 50% time on `most_suitable_rule`

## v2.10.1 (2025-05-05)

### Fix

- cache custom app classes

## v2.10.0 (2025-04-22)

### Feat

- support custom class load from CLI

## v2.9.0 (2025-04-16)

### Feat

- record manifest_path that introduced the folder rule
- support env var expansion in some fields

## v2.8.1 (2025-03-04)

### Fix

- --override-sdkconfig-files not working

## v2.8.0 (2025-02-20)

### Feat

- support '--disable-targets'

## v2.7.0 (2025-02-18)

### Feat

- improve debug info with rich

## v2.6.4 (2025-02-14)

### Fix

- collect file not created when no apps built

## v2.6.3 (2025-02-11)

### Fix

- stop returning duplicated apps in `find_apps`
- compare app based on normalized paths
- remove unnecessary check args in dependency-driven-build

## v2.6.2 (2025-01-21)

### Fix

- windows root dir returns '\\' instead of the drive

## v2.6.1 (2025-01-13)

### Fix

- --config-file not refreshed

## v2.6.0 (2025-01-02)

### Feat

- `manifest_rootpath` support env vars expansion

### Fix

- DeprecationWarning: 'count' is passed as positional argument when `re.sub`
- add `py.typed` file to be used in mypy
- negative value for soc caps integer
- **config_file**: recursively load config file for TOML file

## v2.5.3 (2024-10-04)

### Feat

- support --manifest-filepatterns

## v2.5.2 (2024-09-27)

### Fix

- unset CLI argument wrongly overwrite config file settings with default value
- allow unknown fields

## v2.5.1 (2024-09-26)

### Fix

- stop using lambda functions since they cannot be pickled

## v2.5.0 (2024-09-26)

### Feat

- raise exception when chaining `or`/`and` in manifest file if statements
- support `idf-build-apps find` with checking modified manifest files
- support `idf-build-apps dump-manifest-sha`

### Fix

- stop calling `sys.exit` when return code is 0
- load config file before cli arguments and func arguments
- pickle dump default protocol different in python 3.7
- loose env var requirements. `IDF_PATH` not required
- stop print build log as error when build failed due to `--warning-as-error`
- requires typing-extensions below 3.11
- stop wrongly created/deleted temporary build log file

### Refactor

- declare argument once. used in both function, cli, and docs
- move Manifest.ROOTPATH to arguments
- expand @p placeholders in `BuildArguments`

## v2.4.3 (2024-08-07)

### Feat

- set default building target to "all" if `--target` is not specified
- set default paths to current directory if `--paths` is not specified

## v2.4.2 (2024-08-01)

### Feat

- support `--enable-preview-targets`
- support `--include-all-apps` while find_apps
- support `--output-format json` while find_apps
- support `include_disabled_apps` while `find_apps`

### Fix

- ignore specified target if unknown in current ESP-IDF branch instead of raise exception
- correct `post_build` actions for succeeded with warnings builds
- **completions**: fix typos in help

### Refactor

- update deprecated `datetime.utcnow`

## v2.4.1 (2024-06-18)

### Fix

- use esp32c5 mp as default path

## v2.4.0 (2024-06-17)

### Feat

- support esp32c5 soc header
- **cli**: add CLI autocompletions

## v2.3.1 (2024-04-22)

### Fix

- copy sdkconfig file while `_post_build` instead of the final phase of `build_apps`

## v2.3.0 (2024-03-20)

### Feat

- support ignore app dependencies by components

## v2.2.2 (2024-03-13)

### Fix

- skip size json generation for targets in preview

## v2.2.1 (2024-03-04)

### Fix

- override sdkconfig item keep possible double quotes

## v2.2.0 (2024-02-22)

### Feat

- Support switch-like statements in `depends_components`, and `depends_filepatterns`

## v2.1.1 (2024-02-02)

### Fix

- parse the manifest when folder rule is empty

## v2.1.0 (2024-02-01) (yanked)

### Feat

- support postfixes to reuse arrays

### Fix

- wrongly applied to rules which is defined not in parent dir
- same manifest folder rules shouldn't be declared multi times

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

2.x introduces a lot of breaking changes. For a detailed migration guide, please refer to our [Migration From 1.x to 2.x Guide](https://docs.espressif.com/projects/idf-build-apps/en/latest/guides/1.x_to_2.x.html)

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

## v1.1.5 (2024-03-20)

### Fix

- python 2.7 old class
- search sdkconfig path
- improve error message when env var IDF_PATH not set

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
