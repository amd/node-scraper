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


@pytest.fixture
def multi_package_data_lib():
    """Fixture with multiple packages for testing multiple version mismatches."""
    return PackageDataModel(
        version_info={
            "alternatives.x86_64": "1.30-1.fc41",
            "audit-libs.x86_64": "4.0.2-1.fc41",
            "authselect.x86_64": "1.5.0-8.fc41",
            "authselect-libs.x86_64": "1.5.0-8.fc41",
        }
    )


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
    assert res.message == "All packages found and versions matched"


def test_data_multiple_errors_regex(package_analyzer, default_data_lib):
    """Test that detailed error messages are shown for multiple package errors"""
    args = PackageAnalyzerArgs(
        exp_package_ver={
            "missing-package": None,
            "test-ubuntu-package\\.x86_64": "2\\.\\d+",
            "another-missing": "1\\.0",
        },
        regex_match=True,
    )
    res = package_analyzer.analyze_data(default_data_lib, args=args)
    assert res.status == ExecutionStatus.ERROR
    assert "missing-package" in res.message
    assert "another-missing" in res.message
    assert len(res.events) == 3


def test_data_version_mismatch_exact(package_analyzer, default_data_lib):
    """Exact match: wrong version reported."""
    args = PackageAnalyzerArgs(
        exp_package_ver={"test-ubuntu-package.x86_64": "130-1.xx11"}, regex_match=False
    )
    res = package_analyzer.analyze_data(default_data_lib, args=args)
    assert res.status == ExecutionStatus.ERROR
    assert len(res.events) == 1
    assert res.events[0].data == {
        "expected_package": "test-ubuntu-package.x86_64",
        "expected_version": "130-1.xx11",
        "found_version": "1.11-1.xx11",
        "found_package": "test-ubuntu-package.x86_64",
        "task_name": "PackageAnalyzer",
        "task_type": "DATA_ANALYZER",
    }


def test_data_key_missing_exact(package_analyzer, default_data_lib):
    """Exact match: key typo so package not found."""
    args = PackageAnalyzerArgs(
        exp_package_ver={"test-ubuntu-package.x86_64-typo": "1.11-1.xx11"},
        regex_match=False,
    )
    res = package_analyzer.analyze_data(default_data_lib, args=args)
    assert res.status == ExecutionStatus.ERROR
    assert len(res.events) == 1
    assert res.events[0].data == {
        "expected_package": "test-ubuntu-package.x86_64-typo",
        "expected_version": "1.11-1.xx11",
        "found_package": None,
        "found_version": None,
        "task_name": "PackageAnalyzer",
        "task_type": "DATA_ANALYZER",
    }


def test_data_key_version_mismatch_exact(package_analyzer, default_data_lib):
    """Exact match: correct key, wrong version."""
    args = PackageAnalyzerArgs(
        exp_package_ver={"test-ubuntu-package.x86_64": "1.0-1.xx11"}, regex_match=False
    )
    res = package_analyzer.analyze_data(default_data_lib, args=args)
    assert res.status == ExecutionStatus.ERROR
    assert len(res.events) == 1
    assert res.events[0].data == {
        "expected_package": "test-ubuntu-package.x86_64",
        "expected_version": "1.0-1.xx11",
        "found_version": "1.11-1.xx11",
        "found_package": "test-ubuntu-package.x86_64",
        "task_name": "PackageAnalyzer",
        "task_type": "DATA_ANALYZER",
    }


def test_multiple_versions_mismatch(package_analyzer, multi_package_data_lib):
    """Exact match: multiple packages with wrong versions or missing keys."""
    args = PackageAnalyzerArgs(
        exp_package_ver={
            "alternatives.86_64": "1.30-1.fc41",
            "audit-libs.x86_64": "4.0.21.fc41",
            "authselect.x8_64": "1.5.0-8.fc41",
            "authselect-libs.x86_64": "15.0-8.fc41",
        },
        regex_match=False,
    )
    res = package_analyzer.analyze_data(multi_package_data_lib, args=args)
    assert res.status == ExecutionStatus.ERROR
    assert len(res.events) == 4
    assert res.events[1].data == {
        "expected_package": "audit-libs.x86_64",
        "expected_version": "4.0.21.fc41",
        "found_package": "audit-libs.x86_64",
        "found_version": "4.0.2-1.fc41",
        "task_name": "PackageAnalyzer",
        "task_type": "DATA_ANALYZER",
    }


def test_data_regex(package_analyzer, default_data_lib):
    """Regex match (default): literal package/version matches."""
    args = PackageAnalyzerArgs(exp_package_ver={"test-ubuntu-package.x86_64": "1.11-1.xx11"})
    res = package_analyzer.analyze_data(default_data_lib, args=args)
    assert res.status == ExecutionStatus.OK


def test_data_regex_search(package_analyzer, default_data_lib):
    """Regex match: pattern matches package and version."""
    args = PackageAnalyzerArgs(
        exp_package_ver={
            r"test-ubuntu-package\.x86_64": r"1\.\d+-\d+\.\w+\d+",
        },
        regex_match=True,
    )
    res = package_analyzer.analyze_data(default_data_lib, args=args)
    assert res.status == ExecutionStatus.OK


def test_data_key_not_found_regex_search(package_analyzer, default_data_lib):
    """Regex match: package pattern matches nothing."""
    args = PackageAnalyzerArgs(
        exp_package_ver={
            r"ThisPackageDoesntExist\w+": r"1\.\d+-\d+\.\w+\d+",
        },
        regex_match=True,
    )
    res = package_analyzer.analyze_data(default_data_lib, args=args)
    assert res.status == ExecutionStatus.ERROR
    assert len(res.events) == 1
    assert res.events[0].data == {
        "expected_package": r"ThisPackageDoesntExist\w+",
        "expected_version": r"1\.\d+-\d+\.\w+\d+",
        "found_package": None,
        "found_version": None,
        "task_name": "PackageAnalyzer",
        "task_type": "DATA_ANALYZER",
    }


def test_match_any_version(package_analyzer, multi_package_data_lib):
    """Regex match: expected version None means any version; package exists."""
    args = PackageAnalyzerArgs(
        exp_package_ver={r"authselect.*": None},
        regex_match=True,
    )
    res = package_analyzer.analyze_data(multi_package_data_lib, args=args)
    assert res.status == ExecutionStatus.OK


def test_match_any_version_missing(package_analyzer, default_data_lib):
    """Regex match: expected version None but no package matches key pattern."""
    args = PackageAnalyzerArgs(
        exp_package_ver={r"z.*": None},
        regex_match=True,
    )
    res = package_analyzer.analyze_data(default_data_lib, args=args)
    assert res.status == ExecutionStatus.ERROR
    assert len(res.events) == 1
    assert res.events[0].data == {
        "expected_package": "z.*",
        "expected_version": None,
        "found_package": None,
        "found_version": None,
        "task_name": "PackageAnalyzer",
        "task_type": "DATA_ANALYZER",
    }


def test_match_any_version_exact(package_analyzer, multi_package_data_lib):
    """Exact match: expected version None means any version; package exists."""
    args = PackageAnalyzerArgs(
        exp_package_ver={"authselect.x86_64": None},
        regex_match=False,
    )
    res = package_analyzer.analyze_data(multi_package_data_lib, args=args)
    assert res.status == ExecutionStatus.OK


def test_mismatch_any_version_exact(package_analyzer, default_data_lib):
    """Exact match: expected version None but package key not found."""
    args = PackageAnalyzerArgs(
        exp_package_ver={"uthselect.x86_64": None},
        regex_match=False,
    )
    res = package_analyzer.analyze_data(default_data_lib, args=args)
    assert res.status == ExecutionStatus.ERROR
    assert len(res.events) == 1
    assert res.events[0].data == {
        "expected_package": "uthselect.x86_64",
        "expected_version": None,
        "found_package": None,
        "found_version": None,
        "task_name": "PackageAnalyzer",
        "task_type": "DATA_ANALYZER",
    }


def test_bad_regex_compile(package_analyzer, default_data_lib):
    """Invalid regex pattern yields regex compile error."""
    args = PackageAnalyzerArgs(
        exp_package_ver={r"++": "1.11-1.xx11"},
        regex_match=True,
    )
    res = package_analyzer.analyze_data(default_data_lib, args=args)
    assert res.status == ExecutionStatus.ERROR
    assert len(res.events) == 1
    assert "expected_package_search" in res.events[0].data
    assert "expected_version_search" in res.events[0].data
