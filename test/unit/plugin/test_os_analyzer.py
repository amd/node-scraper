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

from nodescraper.enums.eventcategory import EventCategory
from nodescraper.enums.eventpriority import EventPriority
from nodescraper.enums.executionstatus import ExecutionStatus
from nodescraper.plugins.inband.os.analyzer_args import OsAnalyzerArgs
from nodescraper.plugins.inband.os.os_analyzer import OsAnalyzer
from nodescraper.plugins.inband.os.osdata import OsDataModel

PLATFORM = "platform_id"


@pytest.fixture
def model_obj():
    return OsDataModel(os_name="Ubuntu 22.04.2 LTS")


@pytest.fixture
def config():
    return {
        "os_name": [
            "Ubuntu 22.04.2 LTS",
            "Ubuntu 24.04.2 LTS",
            "RHEL 8.4",
            "RHEL 8.5",
            "CentOS 8.4",
        ],
        "invalid": "invalid",
    }


@pytest.fixture
def analyzer(system_info):
    return OsAnalyzer(system_info=system_info)


def test_all_good_data(analyzer, model_obj, config):
    args = OsAnalyzerArgs(exp_os=config["os_name"])
    result = analyzer.analyze_data(model_obj, args)
    assert result.status == ExecutionStatus.OK
    assert result.message == "OS name matches expected"
    assert all(
        e.priority not in [EventPriority.WARNING, EventPriority.ERROR, EventPriority.CRITICAL]
        for e in result.events
    )


def test_all_good_data_strings(analyzer, model_obj, config):
    args = OsAnalyzerArgs(exp_os=config["os_name"][0])
    result = analyzer.analyze_data(model_obj, args)
    assert result.status == ExecutionStatus.OK
    assert "OS name matches expected" in result.message
    assert all(
        e.priority not in [EventPriority.WARNING, EventPriority.ERROR, EventPriority.CRITICAL]
        for e in result.events
    )


def test_no_config_data(analyzer, model_obj):
    args = OsAnalyzerArgs()
    result = analyzer.analyze_data(model_obj, args)
    assert result.status == ExecutionStatus.NOT_RAN
    assert len(result.events) == 0


def test_invalid_os(analyzer, config):
    model = OsDataModel(os_name="some invalid os")
    args = OsAnalyzerArgs(exp_os=config["os_name"])
    result = analyzer.analyze_data(model, args)
    assert result.status == ExecutionStatus.ERROR
    assert "OS name mismatch!" in result.message
    for event in result.events:
        assert event.priority == EventPriority.CRITICAL
        assert event.category == EventCategory.OS.value


def test_unexpected_os(analyzer, model_obj):
    args = OsAnalyzerArgs(exp_os=["Windows 10"])
    result = analyzer.analyze_data(model_obj, args)
    assert result.status == ExecutionStatus.ERROR
    assert "OS name mismatch!" in result.message
    for event in result.events:
        assert event.priority == EventPriority.CRITICAL
        assert event.category == EventCategory.OS.value


def test_invalid_config_type(analyzer, model_obj, config):
    args = OsAnalyzerArgs(exp_os=config["invalid"])
    result = analyzer.analyze_data(model_obj, args)
    assert result.status == ExecutionStatus.ERROR


def test_os_name_not_exact_match(analyzer, model_obj):
    args = OsAnalyzerArgs(exp_os="Ubuntu 22", exact_match=False)
    result = analyzer.analyze_data(model_obj, args)
    assert result.status == ExecutionStatus.OK
    assert result.message == "OS name matches expected"
    assert all(
        e.priority not in [EventPriority.WARNING, EventPriority.ERROR, EventPriority.CRITICAL]
        for e in result.events
    )


def test_os_name_not_exact_match_list(analyzer, model_obj):
    args = OsAnalyzerArgs(
        exp_os=["Rocky Linux 9.3 (Blue Onyx)", "CentOS Linux 8", "Ubuntu 22"],
        exact_match=False,
    )
    result = analyzer.analyze_data(model_obj, args)
    assert result.status == ExecutionStatus.OK
    assert result.message == "OS name matches expected"
    assert all(
        e.priority not in [EventPriority.WARNING, EventPriority.ERROR, EventPriority.CRITICAL]
        for e in result.events
    )


def test_os_name_not_exact_match_failure(analyzer, model_obj):
    args = OsAnalyzerArgs(exp_os="Windows", exact_match=False)
    result = analyzer.analyze_data(model_obj, args)
    assert result.status == ExecutionStatus.ERROR
    assert "OS name mismatch!" in result.message
    for event in result.events:
        assert event.priority == EventPriority.CRITICAL
        assert event.category == EventCategory.OS.value


def test_os_name_not_exact_match_failure_list(analyzer, model_obj):
    args = OsAnalyzerArgs(
        exp_os=["Windows", "Ubuntu 24.04.5 LTS", "openSUSE Leap 15.6"],
        exact_match=False,
    )
    result = analyzer.analyze_data(model_obj, args)
    assert result.status == ExecutionStatus.ERROR
    assert "OS name mismatch!" in result.message
    for event in result.events:
        assert event.priority == EventPriority.CRITICAL
        assert event.category == EventCategory.OS.value
