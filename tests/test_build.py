# SPDX-FileCopyrightText: 2022-2023 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0
import shutil

import pytest

from idf_build_apps.app import (
    CMakeApp,
)
from idf_build_apps.constants import (
    IDF_PATH,
)


@pytest.mark.skipif(not shutil.which('idf.py'), reason='idf.py not found')
class TestBuild:
    def test_build_hello_world(self, tmpdir, capsys):
        path = IDF_PATH / 'examples' / 'get-started' / 'hello_world'

        CMakeApp(str(path), 'esp32', work_dir=str(tmpdir / 'test')).build()

        captured = capsys.readouterr()
        assert 'Configuring done' in captured.out
        assert 'Project build complete.' in captured.out

    @pytest.mark.parametrize(
        'depends_on_components, check_component_dependencies, assert_build_done',
        [
            (None, True, True),
            ([], True, False),
            ([], False, True),
            ('fake', True, False),
            ('fake', False, True),
            ('soc', True, True),
            ('soc', False, True),
            (['soc', 'fake'], True, True),
        ],
    )
    def test_build_with_depends_on_components(
        self, tmpdir, capsys, depends_on_components, check_component_dependencies, assert_build_done
    ):
        path = IDF_PATH / 'examples' / 'get-started' / 'hello_world'

        CMakeApp(str(path), 'esp32', work_dir=str(tmpdir / 'test')).build(
            depends_on_components=depends_on_components,
            check_component_dependencies=check_component_dependencies,
        )

        captured = capsys.readouterr()
        assert 'Configuring done' in captured.out
        if assert_build_done:
            assert 'Project build complete.' in captured.out
        else:
            assert 'Project build complete.' not in captured.out


@pytest.mark.skipif(not shutil.which('idf.py'), reason='idf.py not found')
def test_idf_version_keywords_type():
    from idf_build_apps.constants import (
        IDF_VERSION_MAJOR,
        IDF_VERSION_MINOR,
        IDF_VERSION_PATCH,
    )

    assert isinstance(IDF_VERSION_MAJOR, int)
    assert isinstance(IDF_VERSION_MINOR, int)
    assert isinstance(IDF_VERSION_PATCH, int)
