# SPDX-FileCopyrightText: 2022-2025 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import os
import shutil
import subprocess
from copy import (
    deepcopy,
)
from pathlib import Path
from xml.etree import (
    ElementTree,
)

import pytest
from conftest import (
    create_project,
)

from idf_build_apps import (
    build_apps,
    find_apps,
)
from idf_build_apps.app import (
    App,
    CMakeApp,
)
from idf_build_apps.args import BuildArguments
from idf_build_apps.constants import (
    IDF_PATH,
    BuildStatus,
)
from idf_build_apps.utils import Literal


@pytest.mark.skipif(not shutil.which('idf.py'), reason='idf.py not found')
class TestBuild:
    def test_build_hello_world(self, tmp_path, capsys):
        path = os.path.join(IDF_PATH, 'examples', 'get-started', 'hello_world')

        app = CMakeApp(path, 'esp32', work_dir=str(tmp_path / 'test'))
        app.build()

        captured = capsys.readouterr()
        assert 'Configuring done' in captured.out
        assert 'Project build complete.' in captured.out
        assert app.build_status == BuildStatus.SUCCESS

    @pytest.mark.parametrize(
        'modified_components, check_app_dependencies, build_status',
        [
            (None, True, BuildStatus.SUCCESS),
            ([], True, BuildStatus.SKIPPED),
            ([], False, BuildStatus.SUCCESS),
            ('fake', True, BuildStatus.SKIPPED),
            ('fake', False, BuildStatus.SUCCESS),
            ('soc', True, BuildStatus.SUCCESS),
            ('soc', False, BuildStatus.SUCCESS),
            (['soc', 'fake'], True, BuildStatus.SUCCESS),
        ],
    )
    def test_build_with_modified_components(self, tmp_path, modified_components, check_app_dependencies, build_status):
        path = os.path.join(IDF_PATH, 'examples', 'get-started', 'hello_world')

        app = CMakeApp(path, 'esp32', work_dir=str(tmp_path / 'test'))
        app.build(
            modified_components=modified_components,
            check_app_dependencies=check_app_dependencies,
        )
        assert app.build_status == build_status

    @pytest.mark.parametrize(
        'modified_files, build_status',
        [
            ('/foo', BuildStatus.SKIPPED),
            (os.path.join(IDF_PATH, 'examples', 'README.md'), BuildStatus.SKIPPED),
            ([os.path.join(IDF_PATH, 'examples', 'get-started', 'hello_world', 'README.md')], BuildStatus.SKIPPED),
            (
                [
                    os.path.join(IDF_PATH, 'examples', 'get-started', 'hello_world', 'README.md'),
                    os.path.join(IDF_PATH, 'examples', 'get-started', 'hello_world', 'main', 'hello_world_main.c'),
                ],
                BuildStatus.SUCCESS,
            ),
        ],
    )
    def test_build_with_modified_files(self, modified_files, build_status):
        test_dir = os.path.join(IDF_PATH, 'examples', 'get-started', 'hello_world')

        app = CMakeApp(test_dir, 'esp32')
        app.build(
            modified_components=[],
            modified_files=modified_files,
            check_app_dependencies=True,
        )

        assert app.build_status == build_status

    def test_build_without_modified_components_but_ignored_app_dependency_check(self):
        test_dir = os.path.join(IDF_PATH, 'examples', 'get-started', 'hello_world')

        apps = find_apps(
            test_dir,
            'esp32',
            modified_components=[],
            modified_files=['foo.c'],
            ignore_app_dependencies_filepatterns=['foo.c'],
        )

        for app in apps:
            app.build()
            assert app.build_status == BuildStatus.SUCCESS

    def test_build_with_junit_output(self, tmp_path):
        test_dir = os.path.join(IDF_PATH, 'examples', 'get-started', 'hello_world')

        apps = [
            CMakeApp(test_dir, 'esp32', build_dir='build_1'),
            CMakeApp(test_dir, 'esp32', build_dir='build_2'),
            CMakeApp(test_dir, 'esp32', build_dir='build_3'),
            CMakeApp(test_dir, 'esp32', build_dir='build_4'),
        ]
        apps[2].build_status = BuildStatus.DISABLED
        apps[3].build_status = BuildStatus.SKIPPED

        build_apps(deepcopy(apps), dry_run=True, junitxml=str(tmp_path / 'test.xml'))

        with open('test.xml') as f:
            xml = ElementTree.fromstring(f.read())

        test_suite = xml.findall('testsuite')[0]
        assert test_suite.attrib['tests'] == '0'
        assert test_suite.attrib['failures'] == '0'
        assert test_suite.attrib['errors'] == '0'
        assert test_suite.attrib['skipped'] == '4'

        for i, testcase in enumerate(test_suite.findall('testcase')):
            assert testcase.attrib['name'] == apps[i].build_path
            assert float(testcase.attrib['time']) > 0
            assert testcase.find('skipped') is not None
            if i in (0, 1):
                assert testcase.find('skipped').attrib['message'] == 'dry run'
            elif i == 2:
                assert testcase.find('skipped').attrib['message'] == 'Build disabled. Skipping...'
            elif i == 3:
                assert testcase.find('skipped').attrib['message'] == 'Build skipped. Skipping...'
            else:
                assert False  # not expected

        build_apps(deepcopy(apps), junitxml=str(tmp_path / 'test.xml'))

        with open('test.xml') as f:
            xml = ElementTree.fromstring(f.read())

        test_suite = xml.findall('testsuite')[0]
        assert test_suite.attrib['tests'] == '2'
        assert test_suite.attrib['failures'] == '0'
        assert test_suite.attrib['errors'] == '0'
        assert test_suite.attrib['skipped'] == '2'

        for i, testcase in enumerate(test_suite.findall('testcase')):
            assert float(testcase.attrib['time']) > 0
            assert testcase.attrib['name'] == apps[i].build_path
            assert testcase.find('error') is None
            assert testcase.find('failure') is None
            if i in (0, 1):
                assert testcase.find('skipped') is None
            elif i == 2:
                assert testcase.find('skipped').attrib['message'] == 'Build disabled. Skipping...'
            elif i == 3:
                assert testcase.find('skipped').attrib['message'] == 'Build skipped. Skipping...'
            else:
                assert False  # not expected

    def test_work_dir_inside_relative_app_dir(self, tmp_path):
        create_project('foo', tmp_path)

        os.chdir(tmp_path / 'foo')
        apps = find_apps(
            '.',
            'esp32',
            work_dir=os.path.join('foo', 'bar'),
        )
        build_apps(apps)

        assert len(apps) == 1
        assert apps[0].build_status == BuildStatus.SUCCESS

    def test_build_apps_without_passing_apps(self, tmp_path):
        create_project('foo', tmp_path)

        os.chdir(tmp_path / 'foo')
        ret_code = build_apps(
            target='esp32',
            work_dir=os.path.join('foo', 'bar'),
            junitxml='test.xml',
        )
        assert ret_code == 0

        with open('test.xml') as f:
            xml = ElementTree.fromstring(f.read())

        test_suite = xml.findall('testsuite')[0]
        assert test_suite.attrib['tests'] == '1'
        assert test_suite.attrib['failures'] == '0'
        assert test_suite.attrib['errors'] == '0'
        assert test_suite.attrib['skipped'] == '0'

        assert test_suite.findall('testcase')[0].attrib['name'] == 'foo/bar/build'


class CustomClassApp(App):
    build_system: Literal['custom_class'] = 'custom_class'  # type: ignore

    def build(self, *args, **kwargs):
        # For testing, we'll just create a dummy build directory
        if not self.dry_run:
            os.makedirs(self.build_path, exist_ok=True)
            with open(os.path.join(self.build_path, 'dummy.txt'), 'w') as f:
                f.write('Custom build successful')
        self.build_status = BuildStatus.SUCCESS
        print('Custom build successful')

    @classmethod
    def is_app(cls, path: str) -> bool:  # noqa: ARG003
        return True


@pytest.mark.skipif(not shutil.which('idf.py'), reason='idf.py not found')
class TestBuildWithCustomApp:
    custom_app_code = """
from idf_build_apps import App
import os
from idf_build_apps.constants import BuildStatus
from idf_build_apps.utils import Literal

class CustomApp(App):
    build_system: Literal['custom'] = 'custom'

    def build(self, *args, **kwargs):
        # For testing, we'll just create a dummy build directory
        if not self.dry_run:
            os.makedirs(self.build_path, exist_ok=True)
            with open(os.path.join(self.build_path, 'dummy.txt'), 'w') as f:
                f.write('Custom build successful')
        self.build_status = BuildStatus.SUCCESS
        print('Custom build successful')

    @classmethod
    def is_app(cls, path: str) -> bool:
        return True
    """

    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path: Path, monkeypatch):
        os.chdir(tmp_path)

        test_app = tmp_path / 'test_app'

        test_app.mkdir()
        (test_app / 'main' / 'main.c').parent.mkdir(parents=True)
        (test_app / 'main' / 'main.c').write_text('void app_main() {}')

        # Create a custom app module
        custom_module = tmp_path / 'custom.py'
        custom_module.write_text(self.custom_app_code)

        monkeypatch.setenv('PYTHONPATH', os.getenv('PYTHONPATH', '') + os.pathsep + str(tmp_path))

        return test_app

    def test_custom_app_cli(self, tmp_path):
        subprocess.run(
            [
                'idf-build-apps',
                'build',
                '-p',
                'test_app',
                '--target',
                'esp32',
                '--build-system',
                'custom:CustomApp',
            ],
            check=True,
        )

        assert (tmp_path / 'test_app' / 'build' / 'dummy.txt').exists()
        assert (tmp_path / 'test_app' / 'build' / 'dummy.txt').read_text() == 'Custom build successful'

    def test_custom_app_function(self, tmp_path):
        # Import the custom app class
        # Find and build the app using the imported CustomApp class
        apps = find_apps(
            paths=['test_app'],
            target='esp32',
            build_system=CustomClassApp,
        )

        assert len(apps) == 1
        app = apps[0]
        assert isinstance(app, CustomClassApp)
        assert app.build_system == 'custom_class'

        # Build the app
        app.build()
        assert app.build_status == BuildStatus.SUCCESS
        assert (tmp_path / 'test_app' / 'build' / 'dummy.txt').exists()
        assert (tmp_path / 'test_app' / 'build' / 'dummy.txt').read_text() == 'Custom build successful'


def test_build_apps_collect_files_when_no_apps_built(tmp_path):
    os.chdir(tmp_path)

    build_apps(
        build_arguments=BuildArguments(
            target='esp32',
            collect_app_info_filename='app_info.txt',
            collect_size_info_filename='size_info.txt',
        )
    )

    assert os.path.exists('app_info.txt')
    assert os.path.exists('size_info.txt')
