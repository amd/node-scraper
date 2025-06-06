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
