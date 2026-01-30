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
from nodescraper.plugins.inband.cmdline.analyzer_args import CmdlineAnalyzerArgs
from nodescraper.plugins.inband.cmdline.cmdline_analyzer import CmdlineAnalyzer
from nodescraper.plugins.inband.cmdline.cmdlinedata import CmdlineDataModel


@pytest.fixture
def model_obj():
    return CmdlineDataModel(
        cmdline="BOOT_IMAGE=/boot/testimage-1234 root=UUID=1234 ro panic=0 nowatchdog msr.allow_writes=on nokaslr amdgpu.noretry=1 pci=realloc=off numa_balancing=disable console=ttyS1,115200"
    )


@pytest.fixture
def config():
    return {
        "required_cmdline": [
            "BOOT_IMAGE=/boot/testimage-1234",
            "ro",
        ],
        "banned_cmdline": ["example"],
    }


def test_nominal_with_config(system_info, model_obj, config):
    analyzer = CmdlineAnalyzer(system_info=system_info)
    args = CmdlineAnalyzerArgs(
        required_cmdline=config["required_cmdline"], banned_cmdline=config["banned_cmdline"]
    )
    res = analyzer.analyze_data(model_obj, args)
    assert res.status == ExecutionStatus.OK
    assert len(res.events) == 0


def test_required_missing(system_info, model_obj, config):
    analyzer = CmdlineAnalyzer(system_info=system_info)
    args = CmdlineAnalyzerArgs(
        required_cmdline=["this is required"], banned_cmdline=["banned_cmdline"]
    )
    res = analyzer.analyze_data(model_obj, args)
    assert res.status == ExecutionStatus.ERROR

    for event in res.events:
        assert event.category == EventCategory.OS.value
        assert event.priority in [EventPriority.CRITICAL, EventPriority.ERROR]


def test_banned_found(system_info, model_obj, config):
    analyzer = CmdlineAnalyzer(system_info=system_info)
    args = CmdlineAnalyzerArgs(
        required_cmdline=config["required_cmdline"],
        banned_cmdline=["root=UUID=1234"],
    )
    res = analyzer.analyze_data(model_obj, args)
    assert res.status == ExecutionStatus.ERROR
    for event in res.events:
        assert event.category == EventCategory.OS.value
        assert event.priority in [EventPriority.CRITICAL, EventPriority.ERROR]


def test_missing_data(system_info, model_obj):
    analyzer = CmdlineAnalyzer(system_info=system_info)
    res = analyzer.analyze_data(data=model_obj)  # pass no data
    assert res.status == ExecutionStatus.NOT_RAN
    assert len(res.events) == 0


def test_banned_found_required_missing(system_info, model_obj, config):
    analyzer = CmdlineAnalyzer(system_info=system_info)
    args = CmdlineAnalyzerArgs(
        required_cmdline=config["required_cmdline"],
        banned_cmdline=["root=UUID=1234"],
    )
    res = analyzer.analyze_data(model_obj, args)
    assert res.status == ExecutionStatus.ERROR
    for event in res.events:
        assert event.category == EventCategory.OS.value
        assert event.priority in [EventPriority.CRITICAL, EventPriority.ERROR]


def test_os_override_centos(system_info, model_obj):
    """Test OS override for CentOS"""
    analyzer = CmdlineAnalyzer(system_info=system_info)
    analyzer.os_id = "centos"  # Set OS to centos

    args = CmdlineAnalyzerArgs(
        required_cmdline=["ro"],
        banned_cmdline=["pci=noats"],
        os_overrides={
            "centos": {
                "required_cmdline": {"add": ["pci=bfsort"], "remove": []},
                "banned_cmdline": {"add": [], "remove": []},
            }
        },
    )
    res = analyzer.analyze_data(model_obj, args)

    # Should fail because pci=bfsort is not in cmdline
    assert res.status == ExecutionStatus.ERROR
    # Check that the missing required event includes pci=bfsort
    found_event = False
    for event in res.events:
        if event.data and "missing_required" in event.data:
            assert "pci=bfsort" in event.data["missing_required"]
            found_event = True
    assert found_event


def test_platform_override(system_info, model_obj):
    """Test platform override"""
    system_info.platform = "mi300x"
    analyzer = CmdlineAnalyzer(system_info=system_info)

    args = CmdlineAnalyzerArgs(
        required_cmdline=["ro"],
        banned_cmdline=[],
        platform_overrides={
            "mi300x": {
                "required_cmdline": {"add": ["amd_iommu=on"], "remove": []},
                "banned_cmdline": {"add": ["pci=realloc=off"], "remove": []},
            }
        },
    )
    res = analyzer.analyze_data(model_obj, args)

    # Should fail because pci=realloc=off is in cmdline but banned
    assert res.status == ExecutionStatus.ERROR
    # Check that the found banned event includes pci=realloc=off
    found_event = False
    for event in res.events:
        if event.data and "found_banned" in event.data:
            assert "pci=realloc=off" in event.data["found_banned"]
            found_event = True
    assert found_event


def test_conflict_detection_required_vs_banned(system_info, model_obj):
    """Test conflict detection when parameter is both required and banned"""
    analyzer = CmdlineAnalyzer(system_info=system_info)

    args = CmdlineAnalyzerArgs(
        required_cmdline=["pci=noats"],
        banned_cmdline=[],
        platform_overrides={"X": {"banned_cmdline": {"add": ["pci=noats"], "remove": []}}},
    )
    res = analyzer.analyze_data(model_obj, args)

    # Check that it failed with error
    assert res.status == ExecutionStatus.ERROR

    # Check that conflict events were logged with consistent description
    conflict_found = False
    for event in res.events:
        if event.description == "CmdlineAnalyzer configuration conflict detected":
            conflict_found = True
            assert event.category == EventCategory.RUNTIME.value
            assert event.priority == EventPriority.ERROR
            # Check the conflict details are in data
            assert event.data["error_type"] == "configuration_conflict"
            assert event.data["conflict_type"] == "required_vs_banned"
            assert "pci=noats" in event.data["conflicting_parameters"]
    assert conflict_found, "No conflict event found in results"


def test_conflict_detection_parameter_values(system_info, model_obj):
    """Test conflict detection for conflicting parameter values"""
    system_info.platform = "mi300x"
    analyzer = CmdlineAnalyzer(system_info=system_info)
    analyzer.os_id = "centos"  # Set OS to centos

    args = CmdlineAnalyzerArgs(
        required_cmdline=[],
        banned_cmdline=[],
        os_overrides={"centos": {"required_cmdline": {"add": ["pci=bfsort"], "remove": []}}},
        platform_overrides={"mi300x": {"required_cmdline": {"add": ["pci=noats"], "remove": []}}},
    )
    res = analyzer.analyze_data(model_obj, args)

    # Check that it failed with error
    assert res.status == ExecutionStatus.ERROR

    # Check that conflict events were logged with consistent description
    conflict_found = False
    for event in res.events:
        if event.description == "CmdlineAnalyzer configuration conflict detected":
            conflict_found = True
            assert event.category == EventCategory.RUNTIME.value
            assert event.priority == EventPriority.ERROR
            # Check the conflict details are in data
            assert event.data["error_type"] == "configuration_conflict"
            assert event.data["conflict_type"] == "parameter_value_conflict"
            assert event.data["parameter"] == "pci"
            assert "pci=bfsort" in event.data["conflicting_values"]
            assert "pci=noats" in event.data["conflicting_values"]
    assert conflict_found, "No parameter value conflict event found in results"


def test_remove_override(system_info, model_obj):
    """Test remove functionality in overrides"""
    analyzer = CmdlineAnalyzer(system_info=system_info)
    analyzer.os_id = "ubuntu"

    args = CmdlineAnalyzerArgs(
        required_cmdline=["ro", "panic=0", "amd_iommu=on"],
        banned_cmdline=[],
        os_overrides={"ubuntu": {"required_cmdline": {"add": [], "remove": ["amd_iommu=on"]}}},
    )
    res = analyzer.analyze_data(model_obj, args)

    # Should pass because amd_iommu=on was removed from requirements
    assert res.status == ExecutionStatus.OK


def test_combined_os_and_platform_overrides(system_info, model_obj):
    """Test both OS and platform overrides applied together"""
    system_info.platform = "mi300x"
    analyzer = CmdlineAnalyzer(system_info=system_info)
    analyzer.os_id = "ubuntu"

    args = CmdlineAnalyzerArgs(
        required_cmdline=["ro"],
        banned_cmdline=[],
        os_overrides={"ubuntu": {"required_cmdline": {"add": ["panic=0"], "remove": []}}},
        platform_overrides={"mi300x": {"required_cmdline": {"add": ["nowatchdog"], "remove": []}}},
    )
    res = analyzer.analyze_data(model_obj, args)

    # Should pass because all required (ro, panic=0, nowatchdog) are present
    assert res.status == ExecutionStatus.OK
    assert len(res.events) == 0
