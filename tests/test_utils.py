# SPDX-FileCopyrightText: 2022-2023 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

from pathlib import (
    Path,
)

import pytest

from idf_build_apps.utils import (
    files_matches_patterns,
    get_parallel_start_stop,
    rmdir,
)


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


@pytest.mark.parametrize(
    'total, parallel_count, parallel_index, start, stop',
    [
        (1, 1, 1, 1, 1),
        (1, 2, 2, 2, 1),
        (1, 10, 1, 1, 1),
        (6, 4, 1, 1, 2),
        (6, 4, 2, 3, 4),
        (6, 4, 3, 5, 6),
        (6, 4, 4, 7, 6),
        (10, 10, 9, 9, 9),
        (33, 2, 1, 1, 17),
        (33, 2, 2, 18, 33),
    ],
)
def test_get_parallel_start_stop(total, parallel_count, parallel_index, start, stop):
    assert (start, stop) == get_parallel_start_stop(total, parallel_count, parallel_index)


@pytest.mark.parametrize(
    'files, patterns, rootpath, result',
    [
        ('c.py', '*.py', None, True),
        ('c.py', '*.py', '/a', True),
        ('/a/b/c.py', 'c.py', None, False),
        ('/a/b/c.py', 'c.py', '/a/b', True),
        ('/a/b/../b/c.py', '*.py', None, False),
        ('/a/b/../b/c.py', '*.py', '/a/b', True),
        ('/a/b/../b/c.py', '**/*.py', None, False),
        ('/a/b/../b/c.py', '**/*.py', '/a', True),
        ('c.py', '/a/**/*.py', None, False),
        ('c.py', '/a/**/*.py', '/a', False),
        ('c.py', '/a/**/*.py', '/a/b', True),
        ('/a/b/c.py', '/a/**/*.py', None, True),
        ('/a/b/c.py', '/a/**/*.py', 'foo', True),
    ],
)
def test_files_matches_patterns(files, patterns, rootpath, result):
    assert files_matches_patterns(files, patterns, rootpath) == result
