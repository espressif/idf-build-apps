# SPDX-FileCopyrightText: 2024 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import pytest

from idf_build_apps.args import (
    BuildArguments,
    DependencyDrivenBuildArguments,
    FindArguments,
    FindBuildArguments,
)
from idf_build_apps.constants import IDF_BUILD_APPS_TOML_FN


def test_init_attr_deprecated_by():
    args = DependencyDrivenBuildArguments(
        ignore_app_dependencies_filepatterns=['bar'],
        modified_files=['barfile'],
    )
    assert args.deactivate_dependency_driven_build_by_filepatterns == ['bar']

    args = DependencyDrivenBuildArguments(
        deactivate_dependency_driven_build_by_components=['foo'],
        modified_components=['foocomp'],
    )
    assert args.deactivate_dependency_driven_build_by_components == ['foo']


@pytest.mark.parametrize(
    'kwargs, expected',
    [
        ({'config': 'foo'}, ['foo']),
        ({'config_rules_str': 'bar'}, ['bar']),
        ({'config_rules': ['baz']}, ['baz']),
    ],
)
def test_init_attr_override(kwargs, expected):
    args = FindBuildArguments(
        **kwargs,
    )
    assert args.config_rules == expected


def test_apply_config_with_deprecated_names():
    with open(IDF_BUILD_APPS_TOML_FN, 'w') as fw:
        fw.write("""config = [
    "foo"
]
no_color = true
""")

    args = FindBuildArguments()
    assert args.config_rules == ['foo']


def test_empty_argument():
    args = FindArguments()
    assert args.config_rules is None


def test_build_args_expansion():
    args = BuildArguments(
        parallel_index=2, collect_app_info='@p.txt', junitxml='x_@p.txt', collect_size_info='@p_@p.txt'
    )
    assert args.collect_app_info == '2.txt'
    assert args.junitxml == 'x_2.txt'

    args.parallel_index = 3
    assert args.collect_app_info == '3.txt'
    assert args.junitxml == 'x_3.txt'
    assert args.collect_size_info == '3_3.txt'


def test_func_overwrite_config():
    with open(IDF_BUILD_APPS_TOML_FN, 'w') as fw:
        fw.write("""config = [
        "foo"
    ]
    modified_components = [
        'comp1',
    ]
    no_color = true
    """)

    args = FindArguments(
        config=['bar'],
    )

    assert args.config_rules == ['bar']
    assert args.modified_components == ['comp1']
    assert args.modified_files is None


def test_func_overwrite_toml_overwrite_pyproject_toml():
    with open('pyproject.toml', 'w') as fw:
        fw.write("""[tool.idf-build-apps]
config = [
    "foo"
]
modified_components = [
    'comp1',
]
ignore_app_dependencies_components = [
    'baz'
]
verbose=3
    """)

    with open(IDF_BUILD_APPS_TOML_FN, 'w') as fw:
        fw.write("""config = [
    "bar"
]
modified_files = [
    'file1',
]
        """)

    args = FindArguments(
        modified_components=['comp2'],
    )
    assert args.config_rules == ['bar']
    assert args.modified_components == ['comp2']
    assert args.modified_files == ['file1']
    assert args.verbose == 3
    assert args.deactivate_dependency_driven_build_by_components == ['baz']
