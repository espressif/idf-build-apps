# SPDX-FileCopyrightText: 2024-2026 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0
import os
import sys
from pathlib import Path
from textwrap import dedent
from xml.etree import ElementTree

import pytest
from conftest import create_project

from idf_build_apps.constants import SUPPORTED_TARGETS
from idf_build_apps.main import main
from idf_build_apps.utils import InvalidCommand


@pytest.mark.parametrize(
    'args, expected_error',
    [
        ([], 'the following arguments are required: --manifest-files, --output/-o'),
        (['--output', 'test.sha1'], 'the following arguments are required: --manifest-files'),
        (['--manifest-files', 'test.yml'], 'the following arguments are required: --output'),
        (['--manifest-files', 'test.yml', '--output', 'test.sha1'], None),
    ],
)
def test_manifest_dump_sha_values(
    args, expected_error, sha_of_enable_only_esp32, sha_of_enable_esp32_or_esp32s2, capsys, monkeypatch
):
    Path('test.yml').write_text(
        """
foo:
  enable:
    - if: IDF_TARGET == "esp32"
bar:
  enable:
    - if: IDF_TARGET == "esp32"
baz:
  enable:
    - if: IDF_TARGET == "esp32"
foobar:
  enable:
    - if: IDF_TARGET == "esp32" or IDF_TARGET == "esp32s2"
""",
        encoding='utf8',
    )

    try:
        with monkeypatch.context() as m:
            m.setattr(sys, 'argv', ['idf-build-apps', 'dump-manifest-sha', *args])

            if not expected_error:
                main()
            else:
                main()
    except SystemExit as e:
        if isinstance(e, InvalidCommand):
            actual_error = e.args[0]
        else:
            actual_error = capsys.readouterr().err
    else:
        actual_error = None

    if expected_error:
        assert actual_error is not None
        assert expected_error in str(actual_error)
    else:
        with open('test.sha1') as fr:
            assert fr.read() == (
                f'bar:{sha_of_enable_only_esp32}\n'
                f'baz:{sha_of_enable_only_esp32}\n'
                f'foo:{sha_of_enable_only_esp32}\n'
                f'foobar:{sha_of_enable_esp32_or_esp32s2}\n'
            )


def test_manifest_patterns(tmp_path, monkeypatch, capsys):
    manifest = tmp_path / 'manifest.yml'
    manifest.write_text(
        """foo:
  enable:
    - if: IDF_TARGET == "esp32"
bar:
  enable:
    - if: IDF_TARGET == "esp32"
        """
    )

    with pytest.raises(SystemExit) as e:
        with monkeypatch.context() as m:
            m.setattr(
                sys,
                'argv',
                ['idf-build-apps', 'find', '--manifest-filepatterns', '**.whatever', '**/manifest.yml', '-vv'],
            )
            main()
        assert e.retcode == 0

    _, err = capsys.readouterr()
    assert f'Loading manifest file {os.path.join(tmp_path, "manifest.yml")}' in err
    assert f'"{os.path.join(tmp_path, "foo")}" does not exist' in err
    assert f'"{os.path.join(tmp_path, "bar")}" does not exist' in err


def test_build_include_all_apps(tmp_path, monkeypatch, capsys):
    create_project('foo', tmp_path)

    manifest = tmp_path / 'manifest.yml'
    manifest.write_text(
        dedent("""\
        foo:
          disable:
            - if: IDF_TARGET == "esp32"
        """)
    )

    with monkeypatch.context() as m:
        m.setattr(
            sys,
            'argv',
            [
                'idf-build-apps',
                'build',
                '--paths',
                'foo',
                '--manifest-files',
                str(manifest),
                '--check-manifest-rules',
                '--include-all-apps',
                '--junitxml',
                str(tmp_path / 'junit.xml'),
                '--dry-run',
            ],
        )
        main()

    out, err = capsys.readouterr()
    assert err == ''
    assert 'Disabled the following apps' in out
    assert out.count('Disabled by manifest rule: IDF_TARGET == "esp32"') == 1

    with open(str(tmp_path / 'junit.xml')) as f:
        xml = ElementTree.fromstring(f.read())

    test_suite = xml.findall('testsuite')[0]
    assert test_suite.attrib['tests'] == '0'
    assert test_suite.attrib['failures'] == '0'
    assert test_suite.attrib['errors'] == '0'
    assert test_suite.attrib['skipped'] == str(len(SUPPORTED_TARGETS))

    disabled_testcases = 0

    for case in test_suite.findall('testcase'):
        if case.get('name') != 'foo/build':
            continue

        skipped = case.find('skipped')
        if skipped is None:
            continue

        if skipped.get('message') == 'Disabled by manifest rule: IDF_TARGET == "esp32"':
            disabled_testcases += 1

    assert disabled_testcases == 1
