# SPDX-FileCopyrightText: 2024-2025 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0
import os
from tempfile import NamedTemporaryFile
from xml.etree import ElementTree

import pytest
from conftest import (
    create_project,
)

from idf_build_apps import App
from idf_build_apps.args import (
    BuildArguments,
    DependencyDrivenBuildArguments,
    FindArguments,
    FindBuildArguments,
)
from idf_build_apps.constants import IDF_BUILD_APPS_TOML_FN
from idf_build_apps.main import main


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
""")

    args = FindBuildArguments()
    assert args.config_rules == ['foo']


def test_apply_config_in_parent_dir(tmp_path):
    test_under = tmp_path / 'test_under'
    test_under.mkdir()
    os.chdir(test_under)

    with open(tmp_path / IDF_BUILD_APPS_TOML_FN, 'w') as fw:
        fw.write('target = "esp32"')

    assert FindArguments().target == 'esp32'


def test_apply_config_over_pyproject_toml(tmp_path):
    test_under = tmp_path / 'test_under'
    test_under.mkdir()
    os.chdir(test_under)

    with open(test_under / 'pyproject.toml', 'w') as fw:
        fw.write("""[tool.idf-build-apps]
target = "esp32s2"
""")

    assert FindArguments().target == 'esp32s2'

    with open(tmp_path / IDF_BUILD_APPS_TOML_FN, 'w') as fw:
        fw.write('target = "esp32"')

    assert FindArguments().target == 'esp32'


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


class TestIgnoreWarningFile:
    def test_deprecated_cli(self, monkeypatch, capsys):
        with open('foo.txt', 'w') as fw:
            fw.write('warning:xxx')

        with monkeypatch.context() as m:
            m.setattr('sys.argv', ['idf-build-apps', 'build', '--ignore-warning-file', 'foo.txt'])
            main()

        assert len(App.IGNORE_WARNS_REGEXES) == 1
        assert App.IGNORE_WARNS_REGEXES[0].pattern == 'warning:xxx'

        with open('bar.txt', 'w') as fw:
            fw.write('warning:yyy')

        with monkeypatch.context() as m:
            m.setattr('sys.argv', ['idf-build-apps', 'build', '--ignore-warning-file', 'foo.txt', 'bar.txt'])
            with pytest.raises(SystemExit):
                main()

        assert 'unrecognized arguments: bar.txt' in capsys.readouterr().err

    def test_new_cli(self, monkeypatch):
        with open('foo.txt', 'w') as fw:
            fw.write('warning:xxx')
        with open('bar.txt', 'w') as fw:
            fw.write('warning:yyy')

        with monkeypatch.context() as m:
            m.setattr('sys.argv', ['idf-build-apps', 'build', '--ignore-warning-files', 'foo.txt', 'bar.txt'])
            main()

        assert len(App.IGNORE_WARNS_REGEXES) == 2
        assert App.IGNORE_WARNS_REGEXES[0].pattern == 'warning:xxx'
        assert App.IGNORE_WARNS_REGEXES[1].pattern == 'warning:yyy'

    def test_func_with_str(self):
        with open('foo.txt', 'w') as fw:
            fw.write('warning:xxx')
        with open('bar.txt', 'w') as fw:
            fw.write('warning:yyy')

        BuildArguments(
            ignore_warning_files=['foo.txt', 'bar.txt'],
        )

        assert len(App.IGNORE_WARNS_REGEXES) == 2
        assert App.IGNORE_WARNS_REGEXES[0].pattern == 'warning:xxx'
        assert App.IGNORE_WARNS_REGEXES[1].pattern == 'warning:yyy'

    def test_func_with_fs(self):
        with open('foo.txt', 'w') as fw:
            fw.write('warning:xxx')
        with open('bar.txt', 'w') as fw:
            fw.write('warning:yyy')

        BuildArguments(
            ignore_warning_file=[open('foo.txt'), open('bar.txt')],
        )

        assert len(App.IGNORE_WARNS_REGEXES) == 2
        assert App.IGNORE_WARNS_REGEXES[0].pattern == 'warning:xxx'
        assert App.IGNORE_WARNS_REGEXES[1].pattern == 'warning:yyy'

    def test_ignore_extra_fields(self):
        with open(IDF_BUILD_APPS_TOML_FN, 'w') as fw:
            fw.write("""dry_run = true""")

        args = FindArguments()
        assert not hasattr(args, 'dry_run')

    def test_config_file(self, tmp_path, monkeypatch):
        create_project('foo', tmp_path)

        with open(IDF_BUILD_APPS_TOML_FN, 'w') as fw:
            fw.write("""paths = ["foo"]
target = "esp32"
build_dir = "build_@t"
junitxml = "test.xml"
keep_going = true
""")

        # test basic config
        with monkeypatch.context() as m:
            m.setenv('PATH', 'foo')  # let build fail
            m.setattr('sys.argv', ['idf-build-apps', 'build'])
            with pytest.raises(SystemExit):
                main()

        with open('test.xml') as f:
            xml = ElementTree.fromstring(f.read())
        test_suite = xml.findall('testsuite')[0]
        assert test_suite.attrib['failures'] == '1'
        assert test_suite.attrib['errors'] == '0'
        assert test_suite.attrib['skipped'] == '0'
        assert test_suite.findall('testcase')[0].attrib['name'] == 'foo/build_esp32'

        # test cli overrides config
        with monkeypatch.context() as m:
            m.setenv('PATH', 'foo')  # let build fail
            m.setattr('sys.argv', ['idf-build-apps', 'build', '--build-dir', 'build_hi_@t'])
            with pytest.raises(SystemExit):
                main()

        with open('test.xml') as f:
            xml = ElementTree.fromstring(f.read())
        test_suite = xml.findall('testsuite')[0]
        assert test_suite.attrib['failures'] == '1'
        assert test_suite.attrib['errors'] == '0'
        assert test_suite.attrib['skipped'] == '0'
        assert test_suite.findall('testcase')[0].attrib['name'] == 'foo/build_hi_esp32'

        # test cli action_true
        with monkeypatch.context() as m:
            m.setattr('sys.argv', ['idf-build-apps', 'build', '--dry-run'])
            main()

        with open('test.xml') as f:
            xml = ElementTree.fromstring(f.read())
        test_suite = xml.findall('testsuite')[0]
        assert test_suite.attrib['failures'] == '0'
        assert test_suite.attrib['errors'] == '0'
        assert test_suite.attrib['skipped'] == '1'
        assert test_suite.findall('testcase')[0].attrib['name'] == 'foo/build_esp32'

        # test config store_true set to true
        with open(IDF_BUILD_APPS_TOML_FN, 'a') as fw:
            fw.write('\ndry_run = true\n')

        with monkeypatch.context() as m:
            m.setattr('sys.argv', ['idf-build-apps', 'build'])
            main()

        with open('test.xml') as f:
            xml = ElementTree.fromstring(f.read())
        test_suite = xml.findall('testsuite')[0]
        assert test_suite.attrib['failures'] == '0'
        assert test_suite.attrib['errors'] == '0'
        assert test_suite.attrib['skipped'] == '1'
        assert test_suite.findall('testcase')[0].attrib['name'] == 'foo/build_esp32'

        # test config store_true set to false, but CLI set to true
        with open(IDF_BUILD_APPS_TOML_FN, 'w') as fw:
            fw.write("""paths = ["foo"]
build_dir = "build_@t"
junitxml = "test.xml"
dry_run = false
""")

        with monkeypatch.context() as m:
            m.setattr(
                'sys.argv', ['idf-build-apps', 'build', '--default-build-targets', 'esp32', 'esp32s2', '--dry-run']
            )
            main()

        with open('test.xml') as f:
            xml = ElementTree.fromstring(f.read())
        test_suite = xml.findall('testsuite')[0]
        assert test_suite.attrib['failures'] == '0'
        assert test_suite.attrib['errors'] == '0'
        assert test_suite.attrib['skipped'] == '2'
        assert test_suite.findall('testcase')[0].attrib['name'] == 'foo/build_esp32'
        assert test_suite.findall('testcase')[1].attrib['name'] == 'foo/build_esp32s2'

    def test_config_file_by_cli(self, tmp_path, monkeypatch):
        create_project('foo', tmp_path)
        create_project('bar', tmp_path)

        with open(IDF_BUILD_APPS_TOML_FN, 'w') as fw:
            fw.write('paths = ["foo"]')

        with NamedTemporaryFile(mode='w', suffix='.toml') as ft:
            ft.write('paths = ["bar"]')
            ft.flush()

            with monkeypatch.context() as m:
                m.setattr(
                    'sys.argv',
                    [
                        'idf-build-apps',
                        'build',
                        '-t',
                        'esp32',
                        '--config-file',
                        ft.name,
                        '--junitxml',
                        'test.xml',
                        '--dry-run',
                    ],
                )
                main()

        with open('test.xml') as f:
            xml = ElementTree.fromstring(f.read())
        test_suite = xml.findall('testsuite')[0]
        assert test_suite.attrib['failures'] == '0'
        assert test_suite.attrib['errors'] == '0'
        assert test_suite.attrib['skipped'] == '1'
        assert test_suite.findall('testcase')[0].attrib['name'] == 'bar/build'
