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
from nodescraper.models.systeminfo import OSFamily
from nodescraper.plugins.inband.storage.analyzer_args import StorageAnalyzerArgs
from nodescraper.plugins.inband.storage.storage_analyzer import StorageAnalyzer
from nodescraper.plugins.inband.storage.storagedata import (
    DeviceStorageData,
    StorageDataModel,
)


@pytest.fixture
def model_obj():
    return StorageDataModel(
        storage_data={
            "/dev/nvme0n1p2": DeviceStorageData(
                total=943441641472,
                free=869796294656,
                used=25645850624,
                percent=3,
            )
        }
    )


@pytest.fixture
def multiple_dev():
    return StorageDataModel(
        storage_data={
            "dev1": DeviceStorageData(total=100, free=90, used=10, percent=10),
            "dev2": DeviceStorageData(total=100, free=5, used=95, percent=95),
        }
    )


@pytest.fixture
def analyzer(system_info):
    return StorageAnalyzer(system_info=system_info)


def test_filter_exact_match(analyzer):
    assert analyzer._matches_device_filter("foo", ["foo", "bar"], regex_match=False)
    assert not analyzer._matches_device_filter("baz", ["foo", "bar"], regex_match=False)


def test_filter_regex_match(analyzer):
    assert analyzer._matches_device_filter("disk0", [r"disk\d"], regex_match=True)
    assert not analyzer._matches_device_filter("diskA", [r"disk\d"], regex_match=True)


def test_filter_invalid_regex(analyzer, monkeypatch):
    calls = []
    monkeypatch.setattr(analyzer, "_log_event", lambda **kw: calls.append(kw))
    assert not analyzer._matches_device_filter("somestring", ["[invalid"], regex_match=True)
    assert len(calls) == 1
    event = calls[0]
    assert event["category"] == EventCategory.STORAGE
    assert event["priority"] == EventPriority.ERROR
    assert "Invalid regex pattern" in event["description"]


def test_check_devices_only(analyzer, multiple_dev):
    args = StorageAnalyzerArgs(min_required_free_space_prct=50, check_devices=["dev1"])
    res = analyzer.analyze_data(multiple_dev, args)
    assert res.status == ExecutionStatus.OK


def test_ignore_devices(analyzer, multiple_dev):
    args = StorageAnalyzerArgs(min_required_free_space_prct=50, ignore_devices=["dev2"])
    res = analyzer.analyze_data(multiple_dev, args)
    assert res.status == ExecutionStatus.OK


def test_check_overrides_ignore(analyzer, multiple_dev):
    args = StorageAnalyzerArgs(
        min_required_free_space_prct=50, check_devices=["dev2"], ignore_devices=["dev2", "dev1"]
    )
    res = analyzer.analyze_data(multiple_dev, args)
    assert res.status == ExecutionStatus.ERROR
    assert any(e.category == EventCategory.STORAGE.value for e in res.events)


def test_only_absolute_threshold_fails(analyzer, model_obj):
    args = StorageAnalyzerArgs(min_required_free_space_abs="800GB")
    result = analyzer.analyze_data(model_obj, args)
    assert result.status == ExecutionStatus.OK
    assert "'/dev/nvme0n1p2' has 869.8GB available, 3.0% used" in result.message


def test_only_percentage_threshold_fails(analyzer, model_obj):
    args = StorageAnalyzerArgs(min_required_free_space_prct=99)
    result = analyzer.analyze_data(model_obj, args)
    assert result.status == ExecutionStatus.ERROR
    assert any(event.category == EventCategory.STORAGE.value for event in result.events)
    assert any(event.priority == EventPriority.CRITICAL for event in result.events)


def test_both_abs_and_prct_fail(system_info):
    system_info.os_family = OSFamily.WINDOWS
    analyzer = StorageAnalyzer(system_info=system_info)

    model = StorageDataModel(
        storage_data={
            "C:": DeviceStorageData(
                total=1013310287872,
                free=466435543040,
                used=546874744832,
                percent=53.97,
            )
        }
    )

    args = StorageAnalyzerArgs(min_required_free_space_abs="10GB", min_required_free_space_prct=96)
    result = analyzer.analyze_data(model, args)
    assert result.status == ExecutionStatus.ERROR
    assert "Insufficient disk space" in result.message
    assert len(result.events) == 1
    assert any(e.category == EventCategory.STORAGE.value for e in result.events)
    assert any(e.priority == EventPriority.CRITICAL for e in result.events)

    args2 = StorageAnalyzerArgs(min_required_free_space_prct=40, min_required_dree_space_abs="1GB")
    result2 = analyzer.analyze_data(model, args2)
    assert result2.status == ExecutionStatus.OK


def test_device_filter(analyzer, model_obj):
    model_obj.storage_data["some_device"] = DeviceStorageData(
        total=1000, free=100, used=900, percent=90
    )

    args = StorageAnalyzerArgs(min_required_free_space_prct="20")
    result = analyzer.analyze_data(model_obj, args)
    assert result.status == ExecutionStatus.ERROR
    assert len(result.events) == 1

    args2 = StorageAnalyzerArgs(
        min_required_free_space_prct="20", ignore_devices=["some_device"], regex_match=True
    )
    result2 = analyzer.analyze_data(model_obj, args2)
    assert result2.status == ExecutionStatus.OK
