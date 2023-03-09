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

- Variables start with `SOC_`. The value would be parsed from `IDF_PATH/components/soc/[TARGET]/include/soc/*_caps.h`
- `IDF_TARGET`
- `IDF_VERSION_MAJOR`
- `IDF_VERSION_MINOR`
- `IDF_VERSION_PATCH`
- `INCLUDE_DEFAULT` (The default value of officially supported targets is 1, otherwise is 0)
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
