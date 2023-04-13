# Configuration File

There are many CLI options available for `idf-build-apps`. While these options provide usage flexibility, they also make the CLI command too long and difficult to read. However, a configuration file allows defining all these options in a more readable and maintainable way.

## Where `idf-build-apps` Looks for the file

When using `idf-build-apps` within a Python project, it is recommended to use `pyproject.toml` as the configuration file, as defined by [PEP 518][pep-518]. This file is written in [TOML][toml], a widely used configuration file language. As of Python 3.11, the standard library includes native support for [TOML][toml].

When running `idf-build-apps`, it looks for `pyproject.toml` starting from the current directory. If the file is not found, it searches parent directories until it either finds the file, encounters a `.git` directory, or reaches the root of the file system.

Alternatively, `idf-build-apps` will also look for a file named `.idf_build_apps.toml`, which is recommended for use in non-Python projects.

Besides, you may also specify the configuration file path using the `--config-file <config file path>` CLI option.

## Usage

You may define it in `.idf_build_apps.toml`:

```toml
paths = [
    "components",
    "examples",
]
target = "esp32"
recursive = true

# config rules
config = [
    "sdkconfig.*=",
    "=default",
]

# build related options
build_dir = "build_@t_@w"
```

Or in `pyproject.toml` with `[tool.idf-build-apps]` section:

```toml
[tool.idf-build-apps]
# same content
# ...
```

Running `idf-build-apps build` with any of the configuration methods mentioned is equivalent to the following CLI command:

```shell
idf-build-app build \
  --paths components examples \
  --target esp32 \
  --recursive \
  --config "sdkconfig.*=" --config "=default" \
  --build-dir "build_@t_@w"
```

[TOML][toml] supports native data types. In order to get the config name and type of the corresponding CLI option, you may refer to the help messages by using `idf-build-apps find -h` or `idf-build-apps build -h`.

For instance, the `--paths` CLI option help message shows:

```text
-p PATHS [PATHS ...], --paths PATHS [PATHS ...]
                     One or more paths to look for apps.
                      - default: None
                      - config name: paths
                      - config type: list[str]
```

This indicates that in the configuration file, you should specify it with the name `paths`, and the type should be a "list of strings".

```toml
paths = [
    "foo",
    "bar",
]
```

[toml]: https://toml.io/en/
[pep-518]: https://www.python.org/dev/peps/pep-0518/
