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
from unittest.mock import MagicMock

import pytest

from nodescraper.enums.eventpriority import EventPriority
from nodescraper.enums.executionstatus import ExecutionStatus
from nodescraper.enums.systeminteraction import SystemInteractionLevel
from nodescraper.models.systeminfo import OSFamily
from nodescraper.plugins.inband.device_enumeration.collector_args import (
    DeviceEnumerationCollectorArgs,
)
from nodescraper.plugins.inband.device_enumeration.device_enumeration_collector import (
    DeviceEnumerationCollector,
)
from nodescraper.plugins.inband.device_enumeration.deviceenumdata import (
    DeviceEnumerationDataModel,
)


@pytest.fixture
def device_enumeration_collector(system_info, conn_mock):
    return DeviceEnumerationCollector(
        system_info=system_info,
        system_interaction_level=SystemInteractionLevel.PASSIVE,
        connection=conn_mock,
    )


def test_collect_linux(system_info, device_enumeration_collector):
    """Test linux typical output"""
    system_info.os_family = OSFamily.LINUX

    lscpu_output = "Architecture:        x86_64\nCPU(s):              64\nSocket(s):           2"
    lshw_output = "*-cpu\n  product: AMD EPYC 1234 64-Core Processor"

    device_enumeration_collector._run_sut_cmd = MagicMock(
        side_effect=[
            MagicMock(
                exit_code=0,
                stdout=lscpu_output,
                stderr="",
                command="lscpu",
            ),
            MagicMock(
                exit_code=0,
                stdout="8",
                stderr="",
                command=(
                    "lspci -d 1002: | grep -iE "
                    "'VGA|Display|3D|Processing accelerators|Co-processor|Accelerator' | "
                    "grep -vi 'Virtual Function' | wc -l"
                ),
            ),
            MagicMock(
                exit_code=0,
                stdout="0",
                stderr="",
                command="lspci -d 1002: | grep -i 'Virtual Function' | wc -l",
            ),
            MagicMock(
                exit_code=0,
                stdout=lshw_output,
                stderr="",
                command="lshw",
            ),
        ]
    )

    result, data = device_enumeration_collector.collect_data()
    assert result.status == ExecutionStatus.OK
    assert data == DeviceEnumerationDataModel(
        cpu_count=2, gpu_count=8, vf_count=0, lscpu_output=lscpu_output, lshw_output=lshw_output
    )
    assert (
        len([a for a in result.artifacts if hasattr(a, "filename") and a.filename == "lshw.txt"])
        == 1
    )


def test_collect_windows(system_info, device_enumeration_collector):
    """Test windows typical output"""
    system_info.os_family = OSFamily.WINDOWS

    device_enumeration_collector._run_sut_cmd = MagicMock(
        side_effect=[
            MagicMock(
                exit_code=0,
                stdout="2",
                stderr="",
                command='powershell -Command "(Get-WmiObject -Class Win32_Processor | Measure-Object).Count"',
            ),
            MagicMock(
                exit_code=0,
                stdout="8",
                stderr="",
                command='powershell -Command "(wmic path win32_VideoController get name | findstr AMD | Measure-Object).Count"',
            ),
            MagicMock(
                exit_code=0,
                stdout="8",
                stderr="",
                command='powershell -Command "(Get-VMHostPartitionableGpu | Measure-Object).Count"',
            ),
        ]
    )

    result, data = device_enumeration_collector.collect_data()
    assert result.status == ExecutionStatus.OK
    assert data == DeviceEnumerationDataModel(cpu_count=2, gpu_count=8, vf_count=8)


def test_collect_error(system_info, device_enumeration_collector):
    """Test with bad exit code"""
    system_info.os_family = OSFamily.LINUX

    device_enumeration_collector._run_sut_cmd = MagicMock(
        side_effect=[
            MagicMock(
                exit_code=1,
                stdout="",
                stderr="command failed",
                command="lscpu",
            ),
            MagicMock(
                exit_code=1,
                stdout="some output",
                stderr="command failed",
                command=(
                    "lspci -d 1002: | grep -iE "
                    "'VGA|Display|3D|Processing accelerators|Co-processor|Accelerator' | "
                    "grep -vi 'Virtual Function' | wc -l"
                ),
            ),
            MagicMock(
                exit_code=1,
                stdout="some output",
                stderr="command failed",
                command="lspci -d 1002: | grep -i 'Virtual Function' | wc -l",
            ),
            MagicMock(
                exit_code=1,
                stdout="",
                stderr="command failed",
                command="lshw",
            ),
        ]
    )

    result, data = device_enumeration_collector.collect_data()
    assert result.status == ExecutionStatus.EXECUTION_FAILURE
    assert data is None


def test_collect_esxi(system_info, device_enumeration_collector):
    """ESXi counts CPUs via esxcli and GPUs/VFs by device ID from collector args."""
    system_info.os_family = OSFamily.ESXI

    device_enumeration_collector._run_sut_cmd = MagicMock(
        side_effect=[
            MagicMock(exit_code=0, stdout="2\n", stderr="", command="cpu"),
            MagicMock(exit_code=0, stdout="8\n", stderr="", command="gpu"),
            MagicMock(exit_code=0, stdout="0\n", stderr="", command="vf"),
        ]
    )

    args = DeviceEnumerationCollectorArgs(devid_ep=0x75A3, devid_ep_vf=0x75B3)
    result, data = device_enumeration_collector.collect_data(args)

    assert result.status == ExecutionStatus.OK
    assert data == DeviceEnumerationDataModel(cpu_count=2, gpu_count=8, vf_count=0)
    # GPU count command must carry the PF device id (hex, unpadded) into the grep.
    gpu_cmd = device_enumeration_collector._run_sut_cmd.call_args_list[1].args[0]
    assert "0x0*75a3" in gpu_cmd
    vf_cmd = device_enumeration_collector._run_sut_cmd.call_args_list[2].args[0]
    assert "0x0*75b3" in vf_cmd


def test_collect_esxi_no_devid(system_info, device_enumeration_collector):
    """Without a devid_ep the ESXi run warns and does not match GPUs by device id."""
    system_info.os_family = OSFamily.ESXI

    device_enumeration_collector._run_sut_cmd = MagicMock(
        side_effect=[
            MagicMock(exit_code=0, stdout="2\n", stderr="", command="cpu"),
            MagicMock(exit_code=0, stdout="0\n", stderr="", command="gpu"),
            MagicMock(exit_code=0, stdout="0\n", stderr="", command="vf"),
        ]
    )

    result, data = device_enumeration_collector.collect_data(DeviceEnumerationCollectorArgs())

    assert result.status == ExecutionStatus.OK
    assert data == DeviceEnumerationDataModel(cpu_count=2, gpu_count=0, vf_count=0)
    assert any("devid_ep not set" in e.description for e in result.events)
    # The unset device id must not be formatted as hex into the grep (no match).
    gpu_cmd = device_enumeration_collector._run_sut_cmd.call_args_list[1].args[0]
    assert "__unset__" in gpu_cmd


def test_collect_esxi_none_args_defaults(system_info, device_enumeration_collector):
    """collect_data(None) on ESXi falls back to default args (devid_ep unset)."""
    system_info.os_family = OSFamily.ESXI
    device_enumeration_collector._run_sut_cmd = MagicMock(
        side_effect=[
            MagicMock(exit_code=0, stdout="2", stderr="", command="cpu"),
            MagicMock(exit_code=0, stdout="0", stderr="", command="gpu"),
            MagicMock(exit_code=0, stdout="0", stderr="", command="vf"),
        ]
    )
    result, data = device_enumeration_collector.collect_data(None)
    assert result.status == ExecutionStatus.OK
    assert data.cpu_count == 2


def test_esxi_device_count_formats_device_id(device_enumeration_collector):
    """_esxi_device_count renders the id as bare lowercase hex; None -> unmatched sentinel."""
    device_enumeration_collector._run_sut_cmd = MagicMock(
        return_value=MagicMock(exit_code=0, stdout="1", stderr="", command="x")
    )
    device_enumeration_collector._esxi_device_count(0x744C)
    assert "0x0*744c" in device_enumeration_collector._run_sut_cmd.call_args.args[0]

    device_enumeration_collector._run_sut_cmd.reset_mock()
    device_enumeration_collector._esxi_device_count(None)
    assert "__unset__" in device_enumeration_collector._run_sut_cmd.call_args.args[0]


def test_parse_count_valid(device_enumeration_collector):
    """A clean numeric stdout parses to int (with surrounding whitespace stripped)."""
    res = MagicMock(exit_code=0, stdout=" 8 \n", stderr="", command="c")
    assert device_enumeration_collector._parse_count(res, "count") == 8


def test_parse_count_non_numeric(device_enumeration_collector):
    """Non-numeric stdout returns None and warns instead of raising ValueError."""
    res = MagicMock(exit_code=0, stdout="N/A", stderr="", command="c")
    assert device_enumeration_collector._parse_count(res, "count") is None
    assert any(
        e.priority == EventPriority.WARNING for e in device_enumeration_collector.result.events
    )


def test_parse_count_bad_exit(device_enumeration_collector):
    """A non-zero exit returns None and warns."""
    res = MagicMock(exit_code=1, stdout="", stderr="boom", command="c")
    assert device_enumeration_collector._parse_count(res, "count") is None
    assert any(
        e.priority == EventPriority.WARNING for e in device_enumeration_collector.result.events
    )
