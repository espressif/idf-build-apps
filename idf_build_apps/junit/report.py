# SPDX-FileCopyrightText: 2023-2025 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

"""
The test report should look like something like this:

.. code-block:: xml

    <testsuites>
        <testsuite
                errors="0"
                failures="1"
                skipped="0"
                tests="29"
                name="Build target esp32 in example folder"
                hostname="GARM-C2-WX-1-R5S4N264"
                time="1051.215"
                timestamp="2022-12-15T13:25:17.689181">
            <testcase
                    file="examples/get_started/hello_world"
                    name="esp32.default.examples/get-started/hello_world"
                    time="60.2454">
                <failure message="build warnings or error message"></failure>
            </testcase>
            <testcase
                    file="examples/get_started/hello_world"
                    name="esp32.default.examples/get-started/hello_world"
                    time="60.2454">
                <skipped message="skipped reason"></skipped>
            </testcase>
        </testsuite>
    </testsuites>
"""

import json
import logging
import os.path
import typing as t
from datetime import (
    datetime,
    timezone,
)
from xml.etree import (
    ElementTree,
)
from xml.sax.saxutils import (
    escape,
)

from ..app import (
    App,
)
from ..constants import (
    BuildStatus,
)
from .utils import (
    get_sys_info,
)

LOGGER = logging.getLogger(__name__)


class TestCase:
    def __init__(
        self,
        name: str,
        *,
        error_reason: t.Optional[str] = None,
        failure_reason: t.Optional[str] = None,
        skipped_reason: t.Optional[str] = None,
        properties: t.Optional[t.Dict[str, str]] = None,
        duration_sec: float = 0,
        timestamp: t.Optional[datetime] = None,
    ) -> None:
        self.name = name

        self.failure_reason = failure_reason
        self.skipped_reason = skipped_reason
        self.error_reason = error_reason
        # only have one reason among these three
        if sum([self.failure_reason is not None, self.skipped_reason is not None, self.error_reason is not None]) > 1:
            raise ValueError('Only one of failure_reason, skipped_reason, error_reason can be set')

        self.duration_sec = duration_sec
        self.timestamp = timestamp or datetime.now(timezone.utc)

        self.properties = properties or {}

    @classmethod
    def from_app(cls, app: App) -> 'TestCase':
        if app.build_status in (BuildStatus.UNKNOWN, BuildStatus.SHOULD_BE_BUILT):
            raise ValueError(
                f'Cannot create build report for apps with build status {app.build_status}. '
                f'Please finish the build process first.'
            )

        kwargs: t.Dict[str, t.Any] = {
            'name': app.build_path,
            'duration_sec': app._build_duration,
            'timestamp': app._build_timestamp,
            'properties': {},
        }
        if app.build_status == BuildStatus.FAILED:
            kwargs['failure_reason'] = app.build_comment
        elif app.build_status in (BuildStatus.DISABLED, BuildStatus.SKIPPED):
            kwargs['skipped_reason'] = app.build_comment

        if app.size_json_path and os.path.isfile(app.size_json_path):
            with open(app.size_json_path) as f:
                for k, v in json.load(f).items():
                    kwargs['properties'][f'{k}'] = str(v)

        return cls(**kwargs)

    @property
    def is_failed(self) -> bool:
        return self.failure_reason is not None

    @property
    def is_skipped(self) -> bool:
        return self.skipped_reason is not None

    @property
    def is_error(self) -> bool:
        return self.error_reason is not None

    def to_xml_elem(self) -> ElementTree.Element:
        elem = ElementTree.Element(
            'testcase',
            {
                'name': self.name,
                'time': str(self.duration_sec),
                'timestamp': self.timestamp.isoformat(),
            },
        )
        if self.error_reason:
            ElementTree.SubElement(elem, 'error', {'message': escape(self.error_reason)})
        elif self.failure_reason:
            ElementTree.SubElement(elem, 'failure', {'message': escape(self.failure_reason)})
        elif self.skipped_reason:
            ElementTree.SubElement(elem, 'skipped', {'message': escape(self.skipped_reason)})

        if self.properties:
            for k, v in self.properties.items():
                elem.attrib[k] = escape(str(v))

        return elem


class TestSuite:
    def __init__(self, name: str) -> None:
        self.name = name

        self.test_cases: t.List[TestCase] = []

        self.tests = 0  # passed, actually
        self.errors = 0  # setup error
        self.failures = 0  # runtime failures
        self.skipped = 0

        self.duration_sec: float = 0
        self.timestamp = datetime.now(timezone.utc)

        self.properties = get_sys_info()

    def add_test_case(self, test_case: TestCase) -> None:
        self.test_cases.append(test_case)

        if test_case.is_error:
            self.errors += 1
        elif test_case.is_failed:
            self.failures += 1
        elif test_case.is_skipped:
            self.skipped += 1
        else:
            self.tests += 1

        self.duration_sec += test_case.duration_sec

    def to_xml_elem(self) -> ElementTree.Element:
        elem = ElementTree.Element(
            'testsuite',
            {
                'name': self.name,
                'tests': str(self.tests),
                'errors': str(self.errors),
                'failures': str(self.failures),
                'skipped': str(self.skipped),
                'time': str(self.duration_sec),
                'timestamp': self.timestamp.isoformat(),
                **self.properties,
            },
        )

        for test_case in self.test_cases:
            elem.append(test_case.to_xml_elem())

        return elem


class TestReport:
    def __init__(self, test_suites: t.List[TestSuite], filepath: str) -> None:
        self.test_suites: t.List[TestSuite] = test_suites

        self.filepath = filepath

    def create_test_report(self) -> None:
        xml = ElementTree.Element('testsuites')

        for test_suite in self.test_suites:
            xml.append(test_suite.to_xml_elem())

        ElementTree.ElementTree(xml).write(self.filepath, encoding='utf-8')
        LOGGER.info('Generated build junit report at: %s', self.filepath)
