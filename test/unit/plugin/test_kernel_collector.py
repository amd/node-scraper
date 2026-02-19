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

from nodescraper.connection.inband.inband import CommandArtifact
from nodescraper.enums.executionstatus import ExecutionStatus
from nodescraper.enums.systeminteraction import SystemInteractionLevel
from nodescraper.models.systeminfo import OSFamily
from nodescraper.plugins.inband.kernel.kernel_collector import KernelCollector
from nodescraper.plugins.inband.kernel.kerneldata import KernelDataModel


@pytest.fixture
def collector(system_info, conn_mock):
    return KernelCollector(
        system_info=system_info,
        system_interaction_level=SystemInteractionLevel.PASSIVE,
        connection=conn_mock,
    )


def test_run_windows(collector, conn_mock):
    collector.system_info.os_family = OSFamily.WINDOWS
    conn_mock.run_command.return_value = CommandArtifact(
        exit_code=0,
        stdout="Version=10.0.19041.1237",
        stderr="",
        command="wmic os get Version /Value",
    )

    result, data = collector.collect_data()

    assert data == KernelDataModel(
        kernel_info="Version=10.0.19041.1237",
        kernel_version="10.0.19041.1237",
        numa_balancing=None,
    )
    assert result.status == ExecutionStatus.OK


def test_run_linux(collector, conn_mock):
    collector.system_info.os_family = OSFamily.LINUX
    conn_mock.run_command.side_effect = [
        CommandArtifact(
            exit_code=0,
            stdout="Linux MockSystem 5.13.0-30-generic #1 XYZ Day Month 10 15:19:13 EDT 2024 x86_64 x86_64 x86_64 GNU/Linux",
            stderr="",
            command="sh -c 'uname -a'",
        ),
        CommandArtifact(
            exit_code=0,
            stdout="0",
            stderr="",
            command="sh -c 'cat /proc/sys/kernel/numa_balancing'",
        ),
    ]

    result, data = collector.collect_data()

    assert data == KernelDataModel(
        kernel_info="Linux MockSystem 5.13.0-30-generic #1 XYZ Day Month 10 15:19:13 EDT 2024 x86_64 x86_64 x86_64 GNU/Linux",
        kernel_version="5.13.0-30-generic",
        numa_balancing=0,
    )
    assert result.status == ExecutionStatus.OK


def test_run_error(collector, conn_mock):
    collector.system_info.os_family = OSFamily.LINUX
    conn_mock.run_command.return_value = CommandArtifact(
        exit_code=1,
        stdout="",
        stderr="Error occurred",
        command="sh -c 'uname -a'",
    )

    result, data = collector.collect_data()

    assert result.status == ExecutionStatus.ERROR
    assert data is None
    assert len(collector.result.events) == 1


def test_run_linux_numa_fails(collector, conn_mock):
    """Linux: uname succeeds but numa_balancing command fails; numa_balancing remains None."""
    collector.system_info.os_family = OSFamily.LINUX
    conn_mock.run_command.side_effect = [
        CommandArtifact(
            exit_code=0,
            stdout="Linux MockSystem 5.4.0-88-generic #1 SMP x86_64 GNU/Linux",
            stderr="",
            command="sh -c 'uname -a'",
        ),
        CommandArtifact(
            exit_code=1,
            stdout="",
            stderr="Permission denied",
            command="sh -c 'cat /proc/sys/kernel/numa_balancing'",
        ),
    ]

    result, data = collector.collect_data()

    assert data == KernelDataModel(
        kernel_info="Linux MockSystem 5.4.0-88-generic #1 SMP x86_64 GNU/Linux",
        kernel_version="5.4.0-88-generic",
        numa_balancing=None,
    )
    assert result.status == ExecutionStatus.OK


def test_run_linux_numa_non_digit(collector, conn_mock):
    """Linux: numa_balancing file returns non-digit; numa_balancing remains None."""
    collector.system_info.os_family = OSFamily.LINUX
    conn_mock.run_command.side_effect = [
        CommandArtifact(
            exit_code=0,
            stdout="Linux host 5.4.0-88-generic #1 SMP x86_64 GNU/Linux",
            stderr="",
            command="sh -c 'uname -a'",
        ),
        CommandArtifact(
            exit_code=0,
            stdout="off\n",
            stderr="",
            command="sh -c 'cat /proc/sys/kernel/numa_balancing'",
        ),
    ]

    result, data = collector.collect_data()

    assert data.kernel_version == "5.4.0-88-generic"
    assert data.numa_balancing is None
    assert result.status == ExecutionStatus.OK
