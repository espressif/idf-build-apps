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
    expand_vars,
)
from idf_build_apps.constants import ALL_TARGETS, IDF_BUILD_APPS_TOML_FN, PREVIEW_TARGETS, SUPPORTED_TARGETS
from idf_build_apps.main import main
from idf_build_apps.manifest.manifest import DEFAULT_BUILD_TARGETS, FolderRule
from idf_build_apps.utils import InvalidCommand


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


def test_build_args_expansion(monkeypatch):
    monkeypatch.setenv('FOO', '2')

    args = BuildArguments(
        parallel_index=2,
        parallel_count='$FOO',
        collect_app_info='@p.txt',
        junitxml='x_@p.txt',
        collect_size_info='@p_@p.txt',
    )
    assert args.collect_app_info == '2.txt'
    assert args.junitxml == 'x_2.txt'
    assert args.parallel_count == 2

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


def test_mutual_exclusivity_validation():
    # Test that both options together raise InvalidCommand
    with pytest.raises(InvalidCommand) as exc_info:
        FindBuildArguments(enable_preview_targets=True, default_build_targets=['esp32'], paths=['.'])

    assert 'Cannot specify both --enable-preview-targets and --default-build-targets' in str(exc_info.value)
    assert 'Please use only one of these options' in str(exc_info.value)


def test_build_targets_cli(tmp_path, monkeypatch):
    create_project('foo', tmp_path)
    with open(IDF_BUILD_APPS_TOML_FN, 'w') as fw:
        fw.write("""paths = ["foo"]
build_dir = "build_@t"
junitxml = "test.xml"
dry_run = true
""")

    def get_enabled_targets(args):
        with monkeypatch.context() as m:
            m.setattr('sys.argv', args)
            main()
        with open('test.xml') as f:
            xml = ElementTree.fromstring(f.read())
        test_suite = xml.findall('testsuite')[0]
        testcases = test_suite.findall('testcase')
        # get targets
        return [c.attrib['name'].replace('foo/build_', '') for c in testcases]

    # default build SUPPORTED_TARGETS
    targets = get_enabled_targets(['idf-build-apps', 'build'])
    assert len(targets) == len(SUPPORTED_TARGETS)
    assert set(targets) == set(SUPPORTED_TARGETS)
    # build with --target
    targets = get_enabled_targets(['idf-build-apps', 'build', '--target', 'esp32'])
    assert len(targets) == 1
    assert targets[0] == 'esp32'
    # build with --default-build-targets
    targets = get_enabled_targets(['idf-build-apps', 'build', '--default-build-targets', 'esp32', 'esp32s2'])
    assert len(targets) == 2
    assert set(targets) == {'esp32', 'esp32s2'}
    # build with --enable-preview-targets
    targets = get_enabled_targets(['idf-build-apps', 'build', '--enable-preview-targets'])
    assert len(targets) == len(SUPPORTED_TARGETS) + len(PREVIEW_TARGETS)
    assert set(targets) == set(SUPPORTED_TARGETS) | set(PREVIEW_TARGETS)
    # build with --disable-targets
    assert 'esp32' in SUPPORTED_TARGETS and 'esp32s2' in SUPPORTED_TARGETS
    targets = get_enabled_targets(['idf-build-apps', 'build', '--disable-targets', 'esp32', 'esp32s2'])
    assert set(targets) == set(SUPPORTED_TARGETS) - {'esp32', 'esp32s2'}
    # build with --enable-preview-targets and --disable-targets
    targets = get_enabled_targets(
        ['idf-build-apps', 'build', '--enable-preview-targets', '--disable-targets', PREVIEW_TARGETS[0]]
    )
    assert len(targets) == len(SUPPORTED_TARGETS) + len(PREVIEW_TARGETS) - 1
    assert set(targets) == set(SUPPORTED_TARGETS) | set(PREVIEW_TARGETS) - {PREVIEW_TARGETS[0]}


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


class TestDefaultBuildTargetsContextVar:
    def test_direct_contextvar_access(self):
        # Test initial value
        assert DEFAULT_BUILD_TARGETS.get() == SUPPORTED_TARGETS

        # Test setting new values
        test_targets = ['esp32', 'esp32s2']
        DEFAULT_BUILD_TARGETS.set(test_targets)
        assert DEFAULT_BUILD_TARGETS.get() == test_targets

        # Test setting to ALL_TARGETS
        DEFAULT_BUILD_TARGETS.set(ALL_TARGETS)
        assert DEFAULT_BUILD_TARGETS.get() == ALL_TARGETS
        assert len(DEFAULT_BUILD_TARGETS.get()) == len(SUPPORTED_TARGETS) + len(PREVIEW_TARGETS)

    def test_folder_rule_backward_compatibility(self):
        # Test initial access
        assert FolderRule.DEFAULT_BUILD_TARGETS == SUPPORTED_TARGETS

        # Test setting via contextvar
        other_targets = ['esp32h2', 'esp32p4']
        DEFAULT_BUILD_TARGETS.set(other_targets)
        assert FolderRule.DEFAULT_BUILD_TARGETS == other_targets
        assert DEFAULT_BUILD_TARGETS.get() == other_targets

        # Test setting via FolderRule
        test_targets = ['esp32c3', 'esp32c6']
        FolderRule.DEFAULT_BUILD_TARGETS = test_targets
        assert DEFAULT_BUILD_TARGETS.get() == test_targets
        assert FolderRule.DEFAULT_BUILD_TARGETS == test_targets

    def test_default_build_targets_option(self):
        """Test that --default-build-targets option works correctly"""
        test_targets = ['esp32', 'esp32s2', 'esp32c3']

        args = FindBuildArguments(default_build_targets=test_targets, paths=['.'])

        assert args.default_build_targets == test_targets
        assert DEFAULT_BUILD_TARGETS.get() == test_targets
        assert FolderRule.DEFAULT_BUILD_TARGETS == test_targets

    def test_enable_preview_targets_option(self):
        """Test that --enable-preview-targets option works correctly"""
        args = FindBuildArguments(enable_preview_targets=True, paths=['.'])

        assert args.enable_preview_targets is True
        assert args.default_build_targets == ALL_TARGETS
        assert DEFAULT_BUILD_TARGETS.get() == ALL_TARGETS
        assert FolderRule.DEFAULT_BUILD_TARGETS == ALL_TARGETS
        assert len(DEFAULT_BUILD_TARGETS.get()) == len(SUPPORTED_TARGETS) + len(PREVIEW_TARGETS)

    def test_default_behavior(self):
        """Test default behavior when no special options are provided"""
        args = FindBuildArguments(paths=['.'])

        assert args.enable_preview_targets is False
        assert args.default_build_targets is None
        assert DEFAULT_BUILD_TARGETS.get() == SUPPORTED_TARGETS
        assert FolderRule.DEFAULT_BUILD_TARGETS == SUPPORTED_TARGETS

    def test_disable_targets_with_default_build_targets(self):
        """Test --disable-targets option works with --default-build-targets"""
        args = FindBuildArguments(
            default_build_targets=['esp32', 'esp32s2', 'esp32c3'], disable_targets=['esp32s2'], paths=['.']
        )

        expected_targets = ['esp32', 'esp32c3']
        assert args.default_build_targets == expected_targets
        assert DEFAULT_BUILD_TARGETS.get() == expected_targets
        assert FolderRule.DEFAULT_BUILD_TARGETS == expected_targets

    def test_disable_targets_with_enable_preview_targets(self):
        """Test --disable-targets option works with --enable-preview-targets"""
        disabled_target = PREVIEW_TARGETS[0]  # Disable first preview target

        args = FindBuildArguments(enable_preview_targets=True, disable_targets=[disabled_target], paths=['.'])

        expected_targets = [t for t in ALL_TARGETS if t != disabled_target]
        assert args.default_build_targets == expected_targets
        assert DEFAULT_BUILD_TARGETS.get() == expected_targets
        assert len(DEFAULT_BUILD_TARGETS.get()) == len(ALL_TARGETS) - 1

    def test_invalid_targets_filtering(self):
        """Test that invalid targets are filtered out and warnings are logged"""
        invalid_targets = ['esp32', 'invalid_target', 'esp32s2', 'another_invalid']

        args = FindBuildArguments(default_build_targets=invalid_targets, paths=['.'])

        # Only valid targets should remain
        expected_targets = ['esp32', 'esp32s2']
        assert args.default_build_targets == expected_targets
        assert DEFAULT_BUILD_TARGETS.get() == expected_targets

    def test_contextvar_isolation_between_instances(self):
        """Test that the contextvar behaves correctly across multiple argument instances"""
        # First instance sets default_build_targets
        FindBuildArguments(default_build_targets=['esp32', 'esp32s2'])
        assert DEFAULT_BUILD_TARGETS.get() == ['esp32', 'esp32s2']

        # Second instance sets enable_preview_targets
        FindBuildArguments(enable_preview_targets=True)
        assert DEFAULT_BUILD_TARGETS.get() == ALL_TARGETS

        # Third instance uses default behavior
        FindBuildArguments()
        assert DEFAULT_BUILD_TARGETS.get() == SUPPORTED_TARGETS

    def test_empty_default_build_targets(self):
        """Test behavior with empty default_build_targets list"""
        args = FindBuildArguments(default_build_targets=[])

        # Empty list is treated as falsy, so it falls back to default behavior
        assert args.default_build_targets == []
        assert DEFAULT_BUILD_TARGETS.get() == SUPPORTED_TARGETS
        assert FolderRule.DEFAULT_BUILD_TARGETS == SUPPORTED_TARGETS


def test_expand_vars(monkeypatch):
    assert expand_vars('Value is $TEST_VAR') == 'Value is '
    monkeypatch.setenv('TEST_VAR', 'test_value')
    assert expand_vars('Value is $TEST_VAR') == 'Value is test_value'
    assert expand_vars('Value is $TEST_VAR and $NON_EXISTING_VAR') == 'Value is test_value and '
    assert expand_vars('No variables here') == 'No variables here'
    assert expand_vars('') == ''


class TestManifestFilepatterns:
    def test_manifest_filepatterns_default(self, tmp_path):
        root_dir = tmp_path / 'project'

        (root_dir / 'app1' / 'manifest.yml').parent.mkdir(parents=True, exist_ok=True)
        (root_dir / 'app1' / 'manifest.yml').write_text('app1:\n  enable:\n    - if: IDF_TARGET == "esp32"')

        (root_dir / 'tests' / 'manifest.yml').parent.mkdir(parents=True, exist_ok=True)
        (root_dir / 'tests' / 'manifest.yml').write_text('tests:\n  enable:\n    - if: IDF_TARGET == "esp32"')

        (root_dir / 'build' / 'managed_components' / 'comp' / 'manifest.yml').parent.mkdir(parents=True, exist_ok=True)
        (root_dir / 'build' / 'managed_components' / 'comp' / 'manifest.yml').write_text(
            'build:\n  enable:\n    - if: IDF_TARGET == "esp32"'
        )

        # Change to the root directory
        os.chdir(root_dir)

        # Test with manifest_filepatterns and default exclude patterns
        args = DependencyDrivenBuildArguments(manifest_filepatterns=['**/*.yml'], manifest_rootpath=str(root_dir))

        # Should include app1 and app2 manifest files, but exclude managed_components
        manifest_files = args.manifest_files
        assert manifest_files is not None
        assert len(manifest_files) == 2

        # Convert to relative paths for easier assertion
        rel_paths = [os.path.relpath(f, str(root_dir)) for f in manifest_files]
        assert 'app1/manifest.yml' in rel_paths
        assert 'tests/manifest.yml' in rel_paths

    def test_manifest_exclude_regexes_custom(self, tmp_path):
        """Test custom exclude patterns"""
        root_dir = tmp_path / 'project'
        root_dir.mkdir()

        # Create various manifest files
        (root_dir / 'app1' / 'manifest.yml').parent.mkdir()
        (root_dir / 'app1' / 'manifest.yml').write_text('app1:\n  enable:\n    - if: IDF_TARGET == "esp32"')

        (root_dir / 'tests' / 'manifest.yml').parent.mkdir()
        (root_dir / 'tests' / 'manifest.yml').write_text('tests:\n  enable:\n    - if: IDF_TARGET == "esp32"')

        (root_dir / 'build' / 'manifest.yml').parent.mkdir()
        (root_dir / 'build' / 'manifest.yml').write_text('build:\n  enable:\n    - if: IDF_TARGET == "esp32"')

        os.chdir(root_dir)

        # Test with custom exclude patterns
        args = DependencyDrivenBuildArguments(
            manifest_filepatterns=['**/*.yml'],
            manifest_exclude_regexes=['/tests/', '/build/'],
            manifest_rootpath=str(root_dir),
        )

        manifest_files = args.manifest_files
        assert manifest_files is not None
        assert len(manifest_files) == 1

        rel_paths = [os.path.relpath(f, str(root_dir)) for f in manifest_files]
        assert 'app1/manifest.yml' in rel_paths

    def test_manifest_exclude_regexes_empty(self, tmp_path):
        """Test with empty exclude patterns"""
        root_dir = tmp_path / 'project'
        root_dir.mkdir()

        # Create manifest files including one in managed_components
        (root_dir / 'app1' / 'manifest.yml').parent.mkdir()
        (root_dir / 'app1' / 'manifest.yml').write_text('app1:\n  enable:\n    - if: IDF_TARGET == "esp32"')

        (root_dir / 'managed_components' / 'component1' / 'manifest.yml').parent.mkdir(parents=True)
        (root_dir / 'managed_components' / 'component1' / 'manifest.yml').write_text(
            'component1:\n  enable:\n    - if: IDF_TARGET == "esp32"'
        )

        os.chdir(root_dir)

        # Test with empty exclude patterns - should include all files
        args = DependencyDrivenBuildArguments(
            manifest_filepatterns=['**/*.yml'], manifest_exclude_regexes=[], manifest_rootpath=str(root_dir)
        )

        manifest_files = args.manifest_files
        assert manifest_files is not None
        assert len(manifest_files) == 2

        rel_paths = [os.path.relpath(f, str(root_dir)) for f in manifest_files]
        assert 'app1/manifest.yml' in rel_paths
        assert 'managed_components/component1/manifest.yml' in rel_paths

    def test_manifest_exclude_regexes_with_existing_manifest_files(self, tmp_path):
        """Test that exclude patterns work when manifest_files are already provided"""
        root_dir = tmp_path / 'project'
        root_dir.mkdir()

        # Create manifest files
        existing_manifest = root_dir / 'existing.yml'
        existing_manifest.write_text('existing:\n  enable:\n    - if: IDF_TARGET == "esp32"')

        (root_dir / 'app1' / 'manifest.yml').parent.mkdir()
        (root_dir / 'app1' / 'manifest.yml').write_text('app1:\n  enable:\n    - if: IDF_TARGET == "esp32"')

        (root_dir / 'managed_components' / 'component1' / 'manifest.yml').parent.mkdir(parents=True)
        (root_dir / 'managed_components' / 'component1' / 'manifest.yml').write_text(
            'component1:\n  enable:\n    - if: IDF_TARGET == "esp32"'
        )

        os.chdir(root_dir)

        # Test with existing manifest files + filepatterns + exclude patterns
        args = DependencyDrivenBuildArguments(
            manifest_files=[str(existing_manifest)],
            manifest_filepatterns=['**/*.yml'],
            manifest_exclude_regexes=['/managed_components/'],
            manifest_rootpath=str(root_dir),
        )

        manifest_files = args.manifest_files
        assert manifest_files is not None
        assert len(manifest_files) == 3  # existing (twice) + app1 (managed_components excluded)

        rel_paths = [os.path.relpath(f, str(root_dir)) for f in manifest_files]
        assert 'existing.yml' in rel_paths
        assert 'app1/manifest.yml' in rel_paths
        assert 'managed_components/component1/manifest.yml' not in rel_paths

    def test_manifest_exclude_regexes_complex_patterns(self, tmp_path):
        """Test complex exclude patterns with wildcards"""
        root_dir = tmp_path / 'project'
        root_dir.mkdir()

        # Create various manifest files
        (root_dir / 'app1' / 'manifest.yml').parent.mkdir()
        (root_dir / 'app1' / 'manifest.yml').write_text('app1:\n  enable:\n    - if: IDF_TARGET == "esp32"')

        (root_dir / 'app2' / 'foo_manifest.yml').parent.mkdir()
        (root_dir / 'app2' / 'foo_manifest.yml').write_text('app2:\n  enable:\n    - if: IDF_TARGET == "esp32"')

        (root_dir / 'docs' / 'example.yml').parent.mkdir()
        (root_dir / 'docs' / 'example.yml').write_text('docs:\n  enable:\n    - if: IDF_TARGET == "esp32"')

        os.chdir(root_dir)

        # Test with complex exclude patterns
        args = DependencyDrivenBuildArguments(
            manifest_filepatterns=['**/*.yml'],
            manifest_exclude_regexes=['/foo_.+', '/docs/'],
            manifest_rootpath=str(root_dir),
        )

        manifest_files = args.manifest_files
        assert manifest_files is not None
        assert len(manifest_files) == 1

        rel_paths = [os.path.relpath(f, str(root_dir)) for f in manifest_files]
        assert 'app1/manifest.yml' in rel_paths
        assert 'app2/foo_manifest.yml' not in rel_paths
        assert 'docs/example.yml' not in rel_paths

    def test_manifest_exclude_regexes_no_filepatterns(self, tmp_path):
        """Test that exclude patterns have no effect when no filepatterns are specified"""
        root_dir = tmp_path / 'project'
        root_dir.mkdir()

        manifest_file = root_dir / 'manifest.yml'
        manifest_file.write_text('app:\n  enable:\n    - if: IDF_TARGET == "esp32"')

        os.chdir(root_dir)

        # Test with only exclude patterns (no filepatterns)
        args = DependencyDrivenBuildArguments(
            manifest_files=[str(manifest_file)], manifest_exclude_regexes=['.+'], manifest_rootpath=str(root_dir)
        )

        # Should still have the explicitly provided manifest file
        manifest_files = args.manifest_files
        assert manifest_files is not None
        assert len(manifest_files) == 1
        assert str(manifest_file) in manifest_files
