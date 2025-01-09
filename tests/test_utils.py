# SPDX-FileCopyrightText: 2022-2025 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0
import os
from pathlib import (
    Path,
)

import pytest

from idf_build_apps.utils import (
    files_matches_patterns,
    get_parallel_start_stop,
    rmdir,
    to_absolute_path,
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
def test_rmdir(tmp_path, patterns, expected):
    test_dir = tmp_path / 'test'
    test_dir.mkdir()
    dir1 = test_dir / 'inner'
    dir1.mkdir()
    (test_dir / 'inner2').mkdir()

    Path(dir1 / 'test.txt').touch()
    Path(dir1 / 'build.log').touch()
    Path(test_dir / 'test.txt').touch()

    rmdir(test_dir, exclude_file_patterns=patterns)

    assert sorted(Path(test_dir).glob('**/*')) == [Path(tmp_path / i) for i in expected]


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


def test_files_matches_patterns(tmp_path):
    # used for testing absolute paths
    temp_dir = tmp_path / 'temp'
    temp_dir.mkdir()
    os.chdir(temp_dir)

    # create real files
    test_dir = tmp_path / 'test'
    test_dir.mkdir()

    a_dir = test_dir / 'a'
    a_dir.mkdir()
    b_dir = a_dir / 'b'
    b_dir.mkdir()
    c_dir = b_dir / 'c'
    c_dir.mkdir()
    b_py = Path(a_dir / 'b.py')
    c_py = Path(b_dir / 'c.py')
    d_py = Path(c_dir / 'd.py')
    b_py.touch()
    c_py.touch()
    d_py.touch()

    # ├── temp
    # └── test
    #     └── a
    #         ├── b
    #         │   ├── c
    #         │   │   └── d.py
    #         │   └── c.py
    #         ├── .hidden
    #         └── b.py
    #

    # in correct relative path
    for matched_files, pat, rootpath in [
        ([b_py], '*.py', a_dir),
        ([b_py, c_py, d_py], '**/*.py', a_dir),
        ([c_py], '*.py', b_dir),
        ([c_py, d_py], '**/*.py', b_dir),
        ([d_py], '*.py', c_dir),
        ([d_py], '**/*.py', c_dir),
    ]:
        for f in matched_files:
            assert files_matches_patterns(f, pat, rootpath)

    # in None root path with relative pattern
    for matched_files, pat in [
        ([b_py], 'a/*.py'),
        ([b_py, c_py, d_py], 'a/**/*.py'),
        ([c_py], 'a/b/*.py'),
        ([c_py, d_py], 'a/b/**/*.py'),
        ([d_py], 'a/b/c/*.py'),
        ([d_py], 'a/b/c/**/*.py'),
    ]:
        for f in matched_files:
            # with correct pwd
            os.chdir(test_dir)
            assert files_matches_patterns(f, pat)

            # with wrong pwd
            os.chdir(temp_dir)
            assert not files_matches_patterns(f, pat)

    # use correct absolute path, in wrong pwd
    for matched_files, pat in [
        ([b_py], 'a/*.py'),
        ([b_py, c_py, d_py], 'a/**/*.py'),
        ([c_py], 'a/b/*.py'),
        ([c_py, d_py], 'a/b/**/*.py'),
        ([d_py], 'a/b/c/*.py'),
        ([d_py], 'a/b/c/**/*.py'),
    ]:
        abs_pat = to_absolute_path(pat, test_dir)
        os.chdir(temp_dir)
        for f in matched_files:
            assert files_matches_patterns(f, abs_pat)
