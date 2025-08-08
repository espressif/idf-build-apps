# SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0


from conftest import create_project

from idf_build_apps.constants import BuildStatus
from idf_build_apps.main import find_apps


class TestBuildDisableReason:
    """Test build disable reason functionality with real projects"""

    def test_manifest_disable_rule_sets_reason(self, tmp_path):
        create_project('test_app', tmp_path)

        manifest_file = tmp_path / 'manifest.yml'
        manifest_file.write_text("""
test_app:
    disable:
        - if: IDF_TARGET == "esp32s3"
          reason: "Not supported on this target"
""")

        apps = find_apps(
            str(tmp_path / 'test_app'), 'esp32s3', manifest_files=[str(manifest_file)], include_disabled_apps=True
        )

        assert len(apps) == 1
        app = apps[0]
        assert app.build_status == BuildStatus.DISABLED
        assert (
            'Disabled by manifest rule: IDF_TARGET == "esp32s3" (reason: Not supported on this target)'
            == app.build_comment
        )

    def test_manifest_enable_only_specific_targets(self, tmp_path):
        """Test that apps not in enable list get proper disable reason"""
        create_project('test_app', tmp_path)

        manifest_file = tmp_path / 'manifest.yml'
        manifest_file.write_text("""
test_app:
    enable:
        - if: IDF_TARGET == "esp32"
        - if: IDF_TARGET == "esp32s2"
""")

        apps = find_apps(
            str(tmp_path / 'test_app'), 'esp32c3', manifest_files=[str(manifest_file)], include_disabled_apps=True
        )

        assert len(apps) == 1
        app = apps[0]
        assert app.build_status == BuildStatus.DISABLED
        assert (
            'Not enabled by manifest rules:\n- IDF_TARGET == "esp32"\n- IDF_TARGET == "esp32s2"'
        ) == app.build_comment

    def test_sdkconfig_target_mismatch_excluded(self, tmp_path):
        """Test that CONFIG_IDF_TARGET mismatch sets proper disable reason"""
        create_project('test_app', tmp_path)

        sdkconfig_file = tmp_path / 'test_app' / 'sdkconfig.defaults'
        sdkconfig_file.write_text('CONFIG_IDF_TARGET="esp32"\n')

        apps = find_apps(str(tmp_path / 'test_app'), 'esp32s2', include_disabled_apps=True)

        assert not apps  # this shall not be disabled. shall be excluded.

    def test_target_not_in_default_build_targets(self, tmp_path):
        """Test that targets not in default build targets get proper disable reason"""
        create_project('test_app', tmp_path)

        apps = find_apps(
            str(tmp_path / 'test_app'),
            'unsupported_target',
            default_build_targets=['esp32', 'esp32s2'],
            include_disabled_apps=True,
        )

        assert len(apps) == 1
        app = apps[0]
        assert app.build_status == BuildStatus.DISABLED
        assert 'Target unsupported_target not in default build targets esp32,esp32s2' == app.build_comment


class TestTestDisableReason:
    """Test test_disable_reason functionality with real projects"""

    def test_no_manifest_no_test_disable(self, tmp_path):
        """Test that apps without manifest don't have test disabling"""
        create_project('test_app', tmp_path)

        apps = find_apps(str(tmp_path / 'test_app'), 'esp32')

        assert len(apps) == 1
        app = apps[0]

        app.check_should_test()

        # Without a manifest, testing should not be disabled
        assert app.test_comment is None

    def test_manifest_disable_test_rule_sets_reason(self, tmp_path):
        """Test that manifest disable_test rules set proper test disable reason"""
        create_project('test_app', tmp_path)

        manifest_file = tmp_path / 'manifest.yml'
        manifest_file.write_text("""
test_app:
    disable_test:
        - if: IDF_TARGET == "esp32c3"
          reason: "Testing not stable on this target"
""")

        # Find the app - should be enabled for building but test disabled
        apps = find_apps(str(tmp_path / 'test_app'), 'esp32c3', manifest_files=[str(manifest_file)])

        assert len(apps) == 1
        app = apps[0]

        # App should be buildable
        assert app.build_status != BuildStatus.DISABLED

        # But testing should be disabled
        app.check_should_test()
        assert (
            'Disabled by manifest rule: IDF_TARGET == "esp32c3" (reason: Testing not stable on this target)'
            == app.test_comment
        )

    def test_manifest_general_disable_affects_test(self, tmp_path):
        """Test that general manifest disable rules also affect testing"""
        create_project('test_app', tmp_path)

        manifest_file = tmp_path / 'manifest.yml'
        manifest_file.write_text("""
test_app:
    disable:
        - if: IDF_TARGET == "esp32h2"
          reason: "Target not supported"
""")

        # Find the app with include_disabled_apps=True to get the disabled app
        apps = find_apps(
            str(tmp_path / 'test_app'), 'esp32h2', manifest_files=[str(manifest_file)], include_disabled_apps=True
        )

        assert len(apps) == 1
        app = apps[0]

        # App should be disabled for building
        assert app.build_status == BuildStatus.DISABLED

        # Testing should also be disabled by the same rule
        app.check_should_test()
        assert app.test_comment is not None
        assert 'Disabled by manifest rule: IDF_TARGET == "esp32h2"' in app.test_comment
        assert '(reason: Target not supported)' in app.test_comment

    def test_manifest_enable_specific_targets_for_test(self, tmp_path):
        """Test that targets not enabled by manifest get proper test disable reason"""
        create_project('test_app', tmp_path)

        manifest_file = tmp_path / 'manifest.yml'
        manifest_file.write_text("""
test_app:
    enable:
        - if: IDF_TARGET == "esp32"
        - if: IDF_TARGET == "esp32s2"
""")

        # Find the app for a target not in the enable list
        apps = find_apps(
            str(tmp_path / 'test_app'), 'esp32s3', manifest_files=[str(manifest_file)], include_disabled_apps=True
        )

        assert len(apps) == 1
        app = apps[0]

        # App should be disabled for building
        assert app.build_status == BuildStatus.DISABLED

        # Testing should also be disabled
        app.check_should_test()
        assert (
            'Not enabled by manifest rules:\n- IDF_TARGET == "esp32"\n- IDF_TARGET == "esp32s2"'
        ) == app.test_comment

    def test_mixed_build_and_test_disable_rules(self, tmp_path):
        """Test apps with both build disable and test-specific disable rules"""
        create_project('build_ok_test_disabled', tmp_path)
        create_project('both_disabled', tmp_path)

        manifest_file = tmp_path / 'manifest.yml'
        manifest_file.write_text("""
build_ok_test_disabled:
    disable_test:
        - if: IDF_TARGET == "esp32c3"
          temporary: true
          reason: "Flaky tests on this hardware"

both_disabled:
    disable:
        - if: IDF_TARGET == "esp32c3"
          reason: "No hardware support"
""")

        apps = find_apps(
            str(tmp_path), 'esp32c3', recursive=True, manifest_files=[str(manifest_file)], include_disabled_apps=True
        )

        # Should find 2 apps
        assert len(apps) == 2

        # Sort by app name for consistent testing
        apps.sort(key=lambda x: x.name)

        # both_disabled: should be disabled for building
        both_disabled_app = apps[0]  # both_disabled comes first alphabetically
        assert both_disabled_app.name == 'both_disabled'
        assert both_disabled_app.build_status == BuildStatus.DISABLED
        assert (
            'Disabled by manifest rule: IDF_TARGET == "esp32c3" (reason: No hardware support)'
            == both_disabled_app.build_comment
        )

        # build_ok_test_disabled: should be OK for building but disabled for testing
        build_ok_app = apps[1]  # build_ok_test_disabled comes second alphabetically
        assert build_ok_app.name == 'build_ok_test_disabled'
        assert build_ok_app.build_status != BuildStatus.DISABLED

        build_ok_app.check_should_test()
        assert (
            'Disabled by manifest rule: IDF_TARGET == "esp32c3" (temporary) (reason: Flaky tests on this hardware)'
            == build_ok_app.test_comment
        )
