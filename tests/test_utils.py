# SPDX-FileCopyrightText: 2022 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path

import pytest

from idf_build_apps.utils import rmdir


@pytest.mark.parametrize(
    'patterns, expected',
    [
        ('*.txt', ['test/inner', 'test/inner/test.txt', 'test/test.txt']),
        (
            ['*.txt', '*.log'],
            [
                'test/inner',
                'test/inner/build.log',
                'test/inner/test.txt',
                'test/test.txt',
            ],
        ),
    ],
)
def test_rmdir(tmpdir, patterns, expected):
    test_dir = tmpdir.mkdir('test')
    dir1 = test_dir.mkdir('inner')
    test_dir.mkdir('inner2')

    Path(dir1 / 'test.txt').touch()
    Path(dir1 / 'build.log').touch()
    Path(test_dir / 'test.txt').touch()

    rmdir(test_dir, exclude_file_patterns=patterns)

    assert sorted(Path(test_dir).glob('**/*')) == [Path(tmpdir / i) for i in expected]
