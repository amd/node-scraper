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

from errorscraper.connection.inband.inband import CommandArtifact
from errorscraper.enums.eventcategory import EventCategory
from errorscraper.enums.executionstatus import ExecutionStatus
from errorscraper.enums.systeminteraction import SystemInteractionLevel
from errorscraper.models.systeminfo import OSFamily
from errorscraper.plugins.inband.memory.memory_collector import MemoryCollector
from errorscraper.plugins.inband.memory.memorydata import MemoryDataModel


@pytest.fixture
def collector(system_info, conn_mock):
    return MemoryCollector(
        system_info=system_info,
        system_interaction_level=SystemInteractionLevel.PASSIVE,
        connection=conn_mock,
    )


def test_run_linux(collector, conn_mock):
    conn_mock.run_command.return_value = CommandArtifact(
        exit_code=0,
        stdout=(
            "            total        used        free      shared  buff/cache   available\n"
            "Mem:    2164113772544 31750934528 2097459761152   893313024 34903076864 2122320150528\n"
            "Swap:    8589930496           0  8589930496"
        ),
        stderr="",
        command="free -h",
    )

    result, data = collector.collect_data()

    assert result.status == ExecutionStatus.OK
    assert data == MemoryDataModel(
        mem_free="2097459761152",
        mem_total="2164113772544",
    )


def test_run_windows(collector, conn_mock):
    collector.system_info.os_family = OSFamily.WINDOWS
    conn_mock.run_command.return_value = CommandArtifact(
        exit_code=0,
        stdout="FreePhysicalMemory=12345678 TotalPhysicalMemory=123412341234",
        stderr="",
        command="wmic OS get FreePhysicalMemory /Value; wmic ComputerSystem get TotalPhysicalMemory /Value",
    )

    result, data = collector.collect_data()

    assert result.status == ExecutionStatus.OK
    assert data == MemoryDataModel(
        mem_free="12345678",
        mem_total="123412341234",
    )


def test_run_error(collector, conn_mock):
    collector.system_info.os_family = OSFamily.LINUX
    conn_mock.run_command.return_value = CommandArtifact(
        exit_code=1,
        stdout=(
            "            total        used        free      shared  buff/cache   available\n"
            "Mem:    2164113772544 31750934528 2097459761152   893313024 34903076864 2122320150528\n"
            "Swap:    8589930496           0  8589930496"
        ),
        stderr="",
        command="free -h",
    )

    result, data = collector.collect_data()

    assert result.status == ExecutionStatus.ERROR
    assert data is None
    assert result.events[0].category == EventCategory.OS.value
    assert result.events[0].description == "Error checking available and total memory"
