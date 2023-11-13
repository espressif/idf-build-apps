# SPDX-FileCopyrightText: 2022-2023 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import os
import shutil
import xml.etree.ElementTree as ET
from copy import (
    deepcopy,
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
    CMakeApp,
)
from idf_build_apps.constants import (
    IDF_PATH,
    BuildStatus,
)


@pytest.mark.skipif(not shutil.which('idf.py'), reason='idf.py not found')
class TestBuild:
    def test_build_hello_world(self, tmpdir, capsys):
        path = IDF_PATH / 'examples' / 'get-started' / 'hello_world'

        app = CMakeApp(str(path), 'esp32', work_dir=str(tmpdir / 'test'))
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
    def test_build_with_modified_components(
        self, tmpdir, capsys, modified_components, check_app_dependencies, build_status
    ):
        path = IDF_PATH / 'examples' / 'get-started' / 'hello_world'

        app = CMakeApp(str(path), 'esp32', work_dir=str(tmpdir / 'test'))
        app.build(
            modified_components=modified_components,
            check_app_dependencies=check_app_dependencies,
        )
        assert app.build_status == build_status

    @pytest.mark.parametrize(
        'modified_files, build_status',
        [
            ('/foo', BuildStatus.SKIPPED),
            (str(IDF_PATH / 'examples' / 'README.md'), BuildStatus.SKIPPED),
            ([str(IDF_PATH / 'examples' / 'get-started' / 'hello_world' / 'README.md')], BuildStatus.SKIPPED),
            (
                [
                    str(IDF_PATH / 'examples' / 'get-started' / 'hello_world' / 'README.md'),
                    str(IDF_PATH / 'examples' / 'get-started' / 'hello_world' / 'main' / 'hello_world_main.c'),
                ],
                BuildStatus.SUCCESS,
            ),
        ],
    )
    def test_build_with_modified_files(self, modified_files, build_status):
        test_dir = str(IDF_PATH / 'examples' / 'get-started' / 'hello_world')

        app = CMakeApp(test_dir, 'esp32')
        app.build(
            modified_components=[],
            modified_files=modified_files,
            check_app_dependencies=True,
        )

        assert app.build_status == build_status

    def test_build_without_modified_components_but_ignored_app_dependency_check(self):
        test_dir = str(IDF_PATH / 'examples' / 'get-started' / 'hello_world')

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

    def test_build_with_junit_output(self, tmpdir):
        test_dir = str(IDF_PATH / 'examples' / 'get-started' / 'hello_world')

        apps = [
            CMakeApp(test_dir, 'esp32', build_dir='build_1'),
            CMakeApp(test_dir, 'esp32', build_dir='build_2'),
        ]

        build_apps(deepcopy(apps), dry_run=True, junitxml=str(tmpdir / 'test.xml'))

        with open(tmpdir / 'test.xml') as f:
            xml = ET.fromstring(f.read())

        test_suite = xml.findall('testsuite')[0]
        assert test_suite.attrib['tests'] == '0'
        assert test_suite.attrib['failures'] == '0'
        assert test_suite.attrib['errors'] == '0'
        assert test_suite.attrib['skipped'] == '2'

        for i, testcase in enumerate(test_suite.findall('testcase')):
            assert testcase.attrib['name'] == apps[i].build_path
            assert float(testcase.attrib['time']) > 0
            assert testcase.find('skipped') is not None
            assert testcase.find('skipped').attrib['message'] == 'dry run'

        build_apps(deepcopy(apps), junitxml=str(tmpdir / 'test.xml'))

        with open(tmpdir / 'test.xml') as f:
            xml = ET.fromstring(f.read())

        test_suite = xml.findall('testsuite')[0]
        assert test_suite.attrib['tests'] == '2'
        assert test_suite.attrib['failures'] == '0'
        assert test_suite.attrib['errors'] == '0'
        assert test_suite.attrib['skipped'] == '0'

        for i, testcase in enumerate(test_suite.findall('testcase')):
            assert testcase.attrib['name'] == apps[i].build_path
            assert float(testcase.attrib['time']) > 0
            assert testcase.find('skipped') is None
            assert testcase.find('error') is None
            assert testcase.find('failure') is None

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
