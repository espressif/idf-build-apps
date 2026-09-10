# Custom App Classes

`idf-build-apps` allows you to create custom app classes by subclassing the base `App` class. This is useful when you need to implement custom build logic or handle special project types.

## Creating a Custom App Class

Here's an example of creating a custom app class:

```python
from idf_build_apps import App
from idf_build_apps.constants import BuildStatus
import os
from typing import Literal


class CustomApp(App):
    build_system: Literal['custom'] = 'custom'  # Must be unique to identify your custom app type

    def build(self, *args, **kwargs):
        # Implement your custom build logic here
        os.makedirs(self.build_path, exist_ok=True)
        with open(os.path.join(self.build_path, 'dummy.txt'), 'w') as f:
            f.write('Custom build successful')
        self.build_status = BuildStatus.SUCCESS
        print('Custom build successful')

    @classmethod
    def is_app(cls, path: str) -> bool:
        # Implement logic to determine if a path contains your custom app type
        return True
```

## Using Custom App Classes

You can use custom app classes in two ways:

### Via CLI

```shell
idf-build-apps build -p /path/to/app --target esp32 --build-system custom:CustomApp
```

Where `custom:CustomApp` is in the format `module:class`. The module must be in your Python path.

### Via Python API

```python
from idf_build_apps import find_apps

apps = find_apps(
    paths=['/path/to/app'],
    target='esp32',
    build_system=CustomApp,
)

for app in apps:
    app.build()
```

## Preparing Apps and Injecting Extra SDKConfig Defaults

Custom app classes can hook into the app discovery process by overriding `prepare_app()` and `extra_sdkconfig_defaults()`:

- `prepare_app(path: str)`: Called once per app directory before `find_apps` expands targets and configurations. Override this class method to generate files needed during discovery (such as board-specific sdkconfig default files).
- `extra_sdkconfig_defaults(path: str)`: Returns a list of additional sdkconfig default files for this app directory. These files are appended after `sdkconfig.defaults` (or `SDKCONFIG_DEFAULTS` / `--sdkconfig-defaults`) and before config-rule files (such as `sdkconfig.ci.*`). Missing files are skipped. Paths can be absolute or relative to the app directory.

### Example: Dynamic Board Defaults

The following example subclasses `CMakeApp` to generate a sdkconfig default file with `CONFIG_IDF_TARGET` during `prepare_app()`. During discovery, the generated defaults file restricts the app to the specified target:

```python
import os
from pathlib import Path
from typing import Literal

from idf_build_apps import CMakeApp
from idf_build_apps import find_apps


class BoardApp(CMakeApp):
    build_system: Literal['board'] = 'board'  # type: ignore

    @classmethod
    def prepare_app(cls, path: str) -> None:
        (Path(path) / 'board_manager.defaults').write_text(
            'CONFIG_IDF_TARGET="esp32s3"\n',
            encoding='utf8',
        )

    @classmethod
    def extra_sdkconfig_defaults(cls, path: str) -> list[str]:
        return [os.path.join(path, 'board_manager.defaults')]


apps = find_apps(
    paths=['/path/to/app'],
    target='all',
    recursive=False,
    default_build_targets=['esp32s3', 'esp32p4'],
    config_rules_str=['sdkconfig.defaults=defaults', 'sdkconfig.ci.*=', '=defaults'],
    build_system=BoardApp,
)
# Only esp32s3 apps are returned; board_manager.defaults appears in app.sdkconfig_files
```

## Important Notes

- Your custom app class must subclass `App` (or a built-in subclass like `CMakeApp`)
- The `build_system` attribute must be unique to identify your app type
- You must implement the `is_app()` class method unless you subclass `CMakeApp` / `MakeApp`
- For JSON serialization support, you need to pass your custom class to `json_to_app()` when deserializing

## Example: JSON Serialization

```python
from idf_build_apps import json_to_app

# Serialize
json_str = custom_app.to_json()

# Deserialize
deserialized_app = json_to_app(json_str, extra_classes=[CustomApp])
```

## Available Methods and Properties

Please refer to the [API reference of the class `App`](https://docs.espressif.com/projects/idf-build-apps/en/latest/references/api/idf_build_apps.html#idf_build_apps.app.App)
