###############################################################################
#
# MIT License
#
# Copyright (c) 2025 Advanced Micro Devices, Inc.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
###############################################################################

import pytest

from nodescraper.enums.executionstatus import ExecutionStatus
from nodescraper.plugins.inband.package.analyzer_args import PackageAnalyzerArgs
from nodescraper.plugins.inband.package.package_analyzer import PackageAnalyzer
from nodescraper.plugins.inband.package.packagedata import PackageDataModel


@pytest.fixture
def package_analyzer(system_info):
    return PackageAnalyzer(system_info)


@pytest.fixture
def default_data_lib():
    return PackageDataModel(version_info={"test-ubuntu-package.x86_64": "1.11-1.xx11"})


def test_no_data(package_analyzer, default_data_lib):
    res = package_analyzer.analyze_data(default_data_lib)
    assert res.status == ExecutionStatus.NOT_RAN


def test_empty_data(package_analyzer, default_data_lib):
    args = PackageAnalyzerArgs(exp_package_ver={})
    res = package_analyzer.analyze_data(default_data_lib, args=args)
    assert res.status == ExecutionStatus.NOT_RAN


def test_empty_data_exact(package_analyzer, default_data_lib):
    args = PackageAnalyzerArgs(exp_package_ver={}, regex_match=False)
    res = package_analyzer.analyze_data(default_data_lib, args=args)
    assert res.status == ExecutionStatus.NOT_RAN


def test_data_exact(package_analyzer, default_data_lib):
    args = PackageAnalyzerArgs(
        exp_package_ver={"test-ubuntu-package.x86_64": "1.11-1.xx11"}, regex_match=False
    )
    res = package_analyzer.analyze_data(default_data_lib, args=args)
    assert res.status == ExecutionStatus.OK


def test_data_version_regex(package_analyzer, default_data_lib):
    args = PackageAnalyzerArgs(
        exp_package_ver={"test-ubuntu-package\\.x86_64": "2\\.\\d+-\\d+\\.\\w+\\d+"},
        regex_match=True,
    )
    res = package_analyzer.analyze_data(default_data_lib, args=args)
    assert res.status == ExecutionStatus.ERROR
    assert len(res.events) == 1
    assert res.events[0].data == {
        "expected_package_search": "test-ubuntu-package\\.x86_64",
        "expected_version_search": "2\\.\\d+-\\d+\\.\\w+\\d+",
        "found_package": "test-ubuntu-package.x86_64",
        "found_version": "1.11-1.xx11",
        "task_name": "PackageAnalyzer",
        "task_type": "DATA_ANALYZER",
    }

    args = PackageAnalyzerArgs(
        exp_package_ver={"test-ubuntu-package\\.x86_64": "1\\.\\d+-\\d+\\.\\w+\\d+"},
        regex_match=True,
    )
    res = package_analyzer.analyze_data(default_data_lib, args=args)
    assert res.status == ExecutionStatus.OK
