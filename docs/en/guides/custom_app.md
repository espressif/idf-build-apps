# Custom App Classes

`idf-build-apps` allows you to create custom app classes by subclassing the base `App` class. This is useful when you need to implement custom build logic or handle special project types.

## Creating a Custom App Class

Here's an example of creating a custom app class:

```python
from idf_build_apps import App
from idf_build_apps.constants import BuildStatus
import os
from typing import Literal  # Python 3.8+ only. from typing_extensions import Literal for earlier versions

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

## Important Notes

- Your custom app class must subclass `App`
- The `build_system` attribute must be unique to identify your app type
- You must implement the `is_app()` class method to identify your app type
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
