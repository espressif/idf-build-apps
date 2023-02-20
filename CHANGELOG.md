# Changelog

All notable changes to this project will be documented in this file.

## [0.3.1]

### Fixed

- Ralative path defined in the manifest files depend on the current work path.

  Added `manifest_rootpath` argument in `find_apps()`. Will use this value instead as the root folder for calculating absolute path.

## [0.3.0]

### Added

- `find_apps`, `build_apps` support `--depends-on-components`, will only find or build apps that require specified components.
- manifest file support `requires_components`

### Fixed

-  Wrong `App.verified_targets` when `CONFIG_IDF_TARGET` set in app's `sdkconfig.defaults` file.

## [0.2.1]

### Fixed

- Fix `--format json` incompatible issue for IDF branches earlier than 5.0
- Fix type annotations incompatible issue for python versions earlier than 3.7
- Fix f-string incompatible issue for python versions earlier than 3.7
- Fix unpack dictionary ending comma syntax error for python 3.4

## [0.2.0]

### Added

- Use `--format json` instead of `--json` with `idf_size.py`
