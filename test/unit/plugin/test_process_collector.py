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
from nodescraper.interfaces.task import SystemCompatibilityError
from nodescraper.models.systeminfo import OSFamily
from nodescraper.plugins.inband.process.process_collector import ProcessCollector
from nodescraper.plugins.inband.process.processdata import ProcessDataModel


@pytest.fixture
def collector(system_info, conn_mock):
    return ProcessCollector(
        system_info=system_info,
        system_interaction_level=SystemInteractionLevel.PASSIVE,
        connection=conn_mock,
    )


def test_run_linux(collector, conn_mock):
    collector.system_info.os_family = OSFamily.LINUX
    conn_mock.run_command.side_effect = [
        MagicMock(
            exit_code=0,
            stdout="PID PROCESS NAME GPU(s) VRAM USED SDMA USED CU OCCUPANCY\n8246 TransferBench 8 2267283456 0 0",
            stderr="",
        ),
        MagicMock(
            exit_code=0,
            stdout="%Cpu(s):  0.1 us,  0.1 sy,  0.0 ni, 90.0 id",
            stderr="",
        ),
        MagicMock(
            exit_code=0,
            stdout="356817 user 20 0 32112 14196 10556 R 10.0 0.0 0:00.07 top\n"
            "1 root 20 0 166596 11916 8316 S 0.0 0.0 1:32.14 systemd",
            stderr="",
        ),
    ]

    result, data = collector.collect_data()
    assert result.status == ExecutionStatus.OK
    assert data == ProcessDataModel(
        kfd_process=1,
        cpu_usage=10,
        processes=[
            ("top", "10.0"),
            ("systemd", "0.0"),
        ],
    )


def test_unsupported_platform(system_info, conn_mock):
    system_info.os_family = OSFamily.WINDOWS
    with pytest.raises(SystemCompatibilityError):
        ProcessCollector(
            system_info=system_info,
            system_interaction_level=SystemInteractionLevel.PASSIVE,
            connection=conn_mock,
        )


def test_exit_failure(collector, conn_mock):
    collector.system_info.os_family = OSFamily.LINUX
    conn_mock.run_command.side_effect = [
        MagicMock(exit_code=1, stdout="", stderr=""),
        MagicMock(exit_code=0, stdout="", stderr=""),
        MagicMock(exit_code=0, stdout="", stderr=""),
    ]

    result, data = collector.collect_data()
    assert result.status == ExecutionStatus.EXECUTION_FAILURE
    assert data is None
