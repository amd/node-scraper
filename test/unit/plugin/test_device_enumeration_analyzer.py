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
from nodescraper.plugins.inband.device_enumeration.analyzer_args import (
    DeviceEnumerationAnalyzerArgs,
)
from nodescraper.plugins.inband.device_enumeration.device_enumeration_analyzer import (
    DeviceEnumerationAnalyzer,
)
from nodescraper.plugins.inband.device_enumeration.deviceenumdata import (
    DeviceEnumerationDataModel,
)


@pytest.fixture
def device_enumeration_analyzer(system_info):
    return DeviceEnumerationAnalyzer(system_info=system_info)


@pytest.fixture
def device_enumeration_data():
    return DeviceEnumerationDataModel(cpu_count=4, gpu_count=4, vf_count=8)


def test_analyze_passing_linux(system_info, device_enumeration_analyzer, device_enumeration_data):
    """Test a normal passing case with matching config"""
    system_info.os_family = OSFamily.LINUX

    args = DeviceEnumerationAnalyzerArgs(cpu_count=4, gpu_count=4, vf_count=8)

    result = device_enumeration_analyzer.analyze_data(data=device_enumeration_data, args=args)

    assert result.status == ExecutionStatus.OK
    assert len(result.events) == 0


def test_analyze_passing_windows(system_info, device_enumeration_analyzer, device_enumeration_data):
    """Test a normal passing case on Windows"""
    system_info.os_family = OSFamily.WINDOWS

    args = DeviceEnumerationAnalyzerArgs(gpu_count=4, vf_count=8)

    result = device_enumeration_analyzer.analyze_data(data=device_enumeration_data, args=args)

    assert result.status == ExecutionStatus.OK
    assert len(result.events) == 0


def test_analyze_no_args(device_enumeration_analyzer, device_enumeration_data):
    """Test with no analyzer args provided - should skip analysis"""

    result = device_enumeration_analyzer.analyze_data(data=device_enumeration_data, args=None)

    assert result.status == ExecutionStatus.NOT_RAN
    assert "Expected Device Enumeration data not provided, skipping analysis." in result.message
    assert len(result.events) == 0


def test_analyze_unexpected_counts(device_enumeration_analyzer, device_enumeration_data):
    """Test with config specifying different device counts"""

    args = DeviceEnumerationAnalyzerArgs(cpu_count=1, gpu_count=10)

    result = device_enumeration_analyzer.analyze_data(data=device_enumeration_data, args=args)

    assert result.status == ExecutionStatus.ERROR
    assert "but got" in result.message

    for event in result.events:
        assert event.priority == EventPriority.CRITICAL
        assert event.category == EventCategory.PLATFORM.value


def test_analyze_mismatched_cpu_count(device_enumeration_analyzer):
    """Test with invalid device enumeration on SUT"""

    data = DeviceEnumerationDataModel(cpu_count=5, gpu_count=4, vf_count=8)
    args = DeviceEnumerationAnalyzerArgs(cpu_count=4, gpu_count=4)

    result = device_enumeration_analyzer.analyze_data(data=data, args=args)

    assert result.status == ExecutionStatus.ERROR
    assert "but got" in result.message

    for event in result.events:
        assert event.priority == EventPriority.CRITICAL
        assert event.category == EventCategory.PLATFORM.value


def test_analyze_list_of_accepted_counts(device_enumeration_analyzer):
    """Test with a list of acceptable counts"""

    data = DeviceEnumerationDataModel(cpu_count=4, gpu_count=4, vf_count=8)
    args = DeviceEnumerationAnalyzerArgs(cpu_count=[2, 4, 8], gpu_count=[4, 8])

    result = device_enumeration_analyzer.analyze_data(data=data, args=args)

    assert result.status == ExecutionStatus.OK
    assert len(result.events) == 0
