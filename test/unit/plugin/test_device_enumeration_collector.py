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

from nodescraper.enums.executionstatus import ExecutionStatus
from nodescraper.enums.systeminteraction import SystemInteractionLevel
from nodescraper.models.systeminfo import OSFamily
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
                stdout="2",
                stderr="",
                command="lscpu | grep Socket | awk '{ print $2 }'",
            ),
            MagicMock(
                exit_code=0,
                stdout="8",
                stderr="",
                command="lspci -d 1002: | grep -i 'VGA\\|Display\\|3D' | wc -l",
            ),
            MagicMock(
                exit_code=0,
                stdout="0",
                stderr="",
                command="lspci -d 1002: | grep -i 'Virtual Function' | wc -l",
            ),
            MagicMock(
                exit_code=0,
                stdout=lscpu_output,
                stderr="",
                command="/usr/bin/lscpu",
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
                stdout="some output",
                stderr="command failed",
                command="lscpu | grep Socket | awk '{ print $2 }'",
            ),
            MagicMock(
                exit_code=1,
                stdout="some output",
                stderr="command failed",
                command="lspci -d 1002: | grep -i 'VGA\\|Display\\|3D' | wc -l",
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
                command="/usr/bin/lscpu",
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
