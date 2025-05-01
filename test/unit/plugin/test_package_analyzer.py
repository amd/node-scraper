import json

import pytest

from errorscraper.enums.executionstatus import ExecutionStatus
from errorscraper.plugins.inband.package.analyzer_args import PackageAnalyzerArgs
from errorscraper.plugins.inband.package.package_analyzer import PackageAnalyzer
from errorscraper.plugins.inband.package.packagedata import PackageDataModel


@pytest.fixture
def package_analyzer(system_info):
    return PackageAnalyzer(system_info)


@pytest.fixture
def package_data(plugin_fixtures_path):
    with (plugin_fixtures_path / "package_example_data.json").open() as fid:
        return json.load(fid)


@pytest.fixture
def default_data_lib(package_data):
    return PackageDataModel(**package_data["ubuntu"])


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
        exp_package_ver={"alternatives.x86_64": "1.11-1.xx11"}, regex_match=False
    )
    res = package_analyzer.analyze_data(default_data_lib, args=args)
    assert res.status == ExecutionStatus.OK


def test_data_version_mismatch_regex(package_analyzer, default_data_lib):
    args = PackageAnalyzerArgs(
        exp_package_ver={"alternatives\\.x86_64": "2\\.\\d+-\\d+\\.\\w+\\d+"}, regex_match=True
    )
    res = package_analyzer.analyze_data(default_data_lib, args=args)
    assert res.status == ExecutionStatus.ERROR
    assert len(res.events) == 1
    assert res.events[0].data == {
        "expected_package_search": "alternatives\\.x86_64",
        "expected_version_search": "2\\.\\d+-\\d+\\.\\w+\\d+",
        "found_package": "alternatives.x86_64",
        "found_version": "1.11-1.xx11",
        "task_name": "PackageAnalyzer",
        "task_type": "DATA_ANALYZER",
    }
