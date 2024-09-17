# SPDX-FileCopyrightText: 2024 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0


from idf_build_apps.args import BuildArguments, DependencyDrivenBuildArguments, FindArguments, FindBuildArguments
from idf_build_apps.config import IDF_BUILD_APPS_TOML_FN


def test_init_attr_deprecated_by(capsys):
    args = DependencyDrivenBuildArguments(
        ignore_app_dependencies_filepatterns=['bar'],
        modified_files=['barfile'],
    )
    assert args.deactivate_dependency_driven_build_by_filepatterns == ['bar']
    assert (
        'Field `ignore_app_dependencies_filepatterns` is deprecated. Will be removed in the next major release. '
        'Use field `deactivate_dependency_driven_build_by_filepatterns` instead'
    ) in capsys.readouterr().err

    args = DependencyDrivenBuildArguments(
        deactivate_dependency_driven_build_by_components=['foo'],
        modified_components=['foocomp'],
    )
    assert args.deactivate_dependency_driven_build_by_components == ['foo']
    # no warning this time
    assert not capsys.readouterr().err


def test_init_attr_override(capsys):
    args = FindBuildArguments(
        config='foo',
        config_rules_str='bar',
        config_rules=['baz'],
    )
    assert args.config_rules == ['baz']
    err_list = capsys.readouterr().err.splitlines()
    assert len(err_list) == 4
    assert (
        'Field `config` is deprecated. Will be removed in the next major release. ' 'Use field `config_rules` instead'
    ) in err_list[0]
    assert 'Field `config_rules` is already set. Ignoring deprecated field `config`' in err_list[1]
    assert (
        'Field `config_rules_str` is deprecated. Will be removed in the next major release. '
        'Use field `config_rules` instead'
    ) in err_list[2]
    assert 'Field `config_rules` is already set. Ignoring deprecated field `config_rules_str`' in err_list[3]


def test_apply_config_with_deprecated_names(tmp_path, capsys):
    with open(tmp_path / IDF_BUILD_APPS_TOML_FN, 'w') as fw:
        fw.write("""config = [
    "foo"
]
no_color = true
""")

    args = FindBuildArguments(config_file=str(tmp_path / IDF_BUILD_APPS_TOML_FN))
    assert args.config_rules == ['foo']
    assert (
        'Field `config` is deprecated. Will be removed in the next major release. ' 'Use field `config_rules` instead'
    ) in capsys.readouterr().err


def test_empty_argument():
    args = FindArguments()
    assert args.config_rules is None


def test_build_args_expansion():
    args = BuildArguments(parallel_index=2)

    args.collect_app_info = '@p.txt'
    assert args.collect_app_info == '2.txt'

    args.parallel_index = 3
    assert args.collect_app_info == '3.txt'

    args.junitxml = 'x_@p.txt'
    assert args.junitxml == 'x_3.txt'

    args.collect_size_info = '@p_@p.txt'
    assert args.collect_size_info == '3_3.txt'
