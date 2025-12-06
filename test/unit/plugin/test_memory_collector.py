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
from nodescraper.enums.eventcategory import EventCategory
from nodescraper.enums.executionstatus import ExecutionStatus
from nodescraper.enums.systeminteraction import SystemInteractionLevel
from nodescraper.models.systeminfo import OSFamily
from nodescraper.plugins.inband.memory.memory_collector import MemoryCollector


@pytest.fixture
def collector(system_info, conn_mock):
    return MemoryCollector(
        system_info=system_info,
        system_interaction_level=SystemInteractionLevel.PASSIVE,
        connection=conn_mock,
    )


def test_run_linux(collector, conn_mock):
    def mock_run_command(command, **kwargs):
        if "free" in command:
            return CommandArtifact(
                exit_code=0,
                stdout=(
                    "            total        used        free      shared  buff/cache   available\n"
                    "Mem:    2164113772544 31750934528 2097459761152   893313024 34903076864 2122320150528\n"
                    "Swap:    8589930496           0  8589930496"
                ),
                stderr="",
                command="free -b",
            )
        elif "lsmem" in command:
            return CommandArtifact(
                exit_code=0,
                stdout=(
                    "RANGE                                 SIZE  STATE REMOVABLE BLOCK\n"
                    "0x0000000000000000-0x000000007fffffff   2G online       yes   0-15\n"
                    "0x0000000100000000-0x000000207fffffff 126G online       yes 32-2047\n"
                    "\n"
                    "Memory block size:       128M\n"
                    "Total online memory:     128G\n"
                    "Total offline memory:      0B\n"
                ),
                stderr="",
                command="/usr/bin/lsmem",
            )
        return CommandArtifact(exit_code=1, stdout="", stderr="", command=command)

    conn_mock.run_command.side_effect = mock_run_command

    result, data = collector.collect_data()

    assert result.status == ExecutionStatus.OK
    assert data.mem_free == "2097459761152"
    assert data.mem_total == "2164113772544"
    assert data.lsmem_output is not None
    assert "memory_blocks" in data.lsmem_output
    assert "summary" in data.lsmem_output
    assert "raw_output" in data.lsmem_output
    assert len(data.lsmem_output["memory_blocks"]) == 2
    assert data.lsmem_output["memory_blocks"][0]["range"] == "0x0000000000000000-0x000000007fffffff"
    assert data.lsmem_output["memory_blocks"][0]["size"] == "2G"
    assert data.lsmem_output["memory_blocks"][0]["state"] == "online"
    assert data.lsmem_output["summary"]["memory_block_size"] == "128M"
    assert data.lsmem_output["summary"]["total_online_memory"] == "128G"


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
    assert data.mem_free == "12345678"
    assert data.mem_total == "123412341234"
    assert data.lsmem_output is None
    assert conn_mock.run_command.call_count == 1


def test_run_linux_lsmem_fails(collector, conn_mock):
    def mock_run_command(command, **kwargs):
        if "free" in command:
            return CommandArtifact(
                exit_code=0,
                stdout=(
                    "            total        used        free      shared  buff/cache   available\n"
                    "Mem:    2164113772544 31750934528 2097459761152   893313024 34903076864 2122320150528\n"
                    "Swap:    8589930496           0  8589930496"
                ),
                stderr="",
                command="free -b",
            )
        elif "lsmem" in command:
            return CommandArtifact(
                exit_code=127,
                stdout="",
                stderr="lsmem: command not found",
                command="/usr/bin/lsmem",
            )
        return CommandArtifact(exit_code=1, stdout="", stderr="", command=command)

    conn_mock.run_command.side_effect = mock_run_command

    result, data = collector.collect_data()

    assert result.status == ExecutionStatus.OK
    assert data.mem_free == "2097459761152"
    assert data.mem_total == "2164113772544"
    assert data.lsmem_output is None
    lsmem_events = [e for e in result.events if "lsmem" in e.description]
    assert len(lsmem_events) > 0


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


def test_parse_lsmem_output(collector):
    """Test parsing of lsmem command output."""
    lsmem_output = (
        "RANGE                                 SIZE  STATE REMOVABLE BLOCK\n"
        "0x0000000000000000-0x000000007fffffff   2G online       yes   0-15\n"
        "0x0000000100000000-0x000000207fffffff 126G online       yes 32-2047\n"
        "0x0000002080000000-0x000000407fffffff 126G online        no 2048-4095\n"
        "\n"
        "Memory block size:       128M\n"
        "Total online memory:     254G\n"
        "Total offline memory:      0B\n"
    )

    result = collector._parse_lsmem_output(lsmem_output)

    assert "raw_output" in result
    assert "memory_blocks" in result
    assert "summary" in result
    assert result["raw_output"] == lsmem_output
    assert len(result["memory_blocks"]) == 3

    assert result["memory_blocks"][0]["range"] == "0x0000000000000000-0x000000007fffffff"
    assert result["memory_blocks"][0]["size"] == "2G"
    assert result["memory_blocks"][0]["state"] == "online"
    assert result["memory_blocks"][0]["removable"] == "yes"
    assert result["memory_blocks"][0]["block"] == "0-15"

    assert result["memory_blocks"][1]["range"] == "0x0000000100000000-0x000000207fffffff"
    assert result["memory_blocks"][1]["size"] == "126G"
    assert result["memory_blocks"][1]["state"] == "online"

    assert result["memory_blocks"][2]["removable"] == "no"
    assert result["memory_blocks"][2]["block"] == "2048-4095"

    assert result["summary"]["memory_block_size"] == "128M"
    assert result["summary"]["total_online_memory"] == "254G"
    assert result["summary"]["total_offline_memory"] == "0B"
