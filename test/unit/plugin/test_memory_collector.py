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
                command="lsmem",
            )
        elif "numactl" in command:
            return CommandArtifact(
                exit_code=0,
                stdout=(
                    "available: 2 nodes (0-1)\n"
                    "node 0 cpus: 0 1 2 3 4 5 6 7\n"
                    "node 0 size: 32768 MB\n"
                    "node 0 free: 16384 MB\n"
                    "node 1 cpus: 8 9 10 11 12 13 14 15\n"
                    "node 1 size: 32768 MB\n"
                    "node 1 free: 20000 MB\n"
                    "node distances:\n"
                    "node   0   1\n"
                    "  0:  10  21\n"
                    "  1:  21  10"
                ),
                stderr="",
                command="numactl -H",
            )
        return CommandArtifact(exit_code=1, stdout="", stderr="", command=command)

    conn_mock.run_command.side_effect = mock_run_command

    result, data = collector.collect_data()

    assert result.status == ExecutionStatus.OK
    assert data.mem_free == "2097459761152"
    assert data.mem_total == "2164113772544"
    assert data.lsmem_data is not None
    assert len(data.lsmem_data.memory_blocks) == 2
    assert data.lsmem_data.memory_blocks[0].range == "0x0000000000000000-0x000000007fffffff"
    assert data.lsmem_data.memory_blocks[0].size == "2G"
    assert data.lsmem_data.memory_blocks[0].state == "online"
    assert data.lsmem_data.summary.memory_block_size == "128M"
    assert data.lsmem_data.summary.total_online_memory == "128G"
    assert data.numa_topology is not None
    assert len(data.numa_topology.nodes) == 2
    assert data.numa_topology.nodes[0].node_id == 0
    assert data.numa_topology.nodes[0].memory_size_mb == 32768
    assert data.numa_topology.distance_matrix[0][1] == 21


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
    assert data.lsmem_data is None
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
                command="lsmem",
            )
        elif "numactl" in command:
            return CommandArtifact(
                exit_code=127,
                stdout="",
                stderr="numactl: command not found",
                command="numactl -H",
            )
        return CommandArtifact(exit_code=1, stdout="", stderr="", command=command)

    conn_mock.run_command.side_effect = mock_run_command

    result, data = collector.collect_data()

    assert result.status == ExecutionStatus.OK
    assert data.mem_free == "2097459761152"
    assert data.mem_total == "2164113772544"
    assert data.lsmem_data is None
    assert data.numa_topology is None
    lsmem_events = [e for e in result.events if "lsmem" in e.description]
    assert len(lsmem_events) > 0
    numactl_events = [e for e in result.events if "numactl" in e.description]
    assert len(numactl_events) > 0


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

    assert result is not None
    assert len(result.memory_blocks) == 3

    assert result.memory_blocks[0].range == "0x0000000000000000-0x000000007fffffff"
    assert result.memory_blocks[0].size == "2G"
    assert result.memory_blocks[0].state == "online"
    assert result.memory_blocks[0].removable == "yes"
    assert result.memory_blocks[0].block == "0-15"

    assert result.memory_blocks[1].range == "0x0000000100000000-0x000000207fffffff"
    assert result.memory_blocks[1].size == "126G"
    assert result.memory_blocks[1].state == "online"

    assert result.memory_blocks[2].removable == "no"
    assert result.memory_blocks[2].block == "2048-4095"

    assert result.summary.memory_block_size == "128M"
    assert result.summary.total_online_memory == "254G"
    assert result.summary.total_offline_memory == "0B"


def test_parse_lsmem_output_no_blocks(collector):
    """Test parsing of lsmem output with no memory blocks."""
    lsmem_output = (
        "RANGE                                 SIZE  STATE REMOVABLE BLOCK\n"
        "\n"
        "Memory block size:       128M\n"
        "Total online memory:     0G\n"
        "Total offline memory:      0B\n"
    )

    result = collector._parse_lsmem_output(lsmem_output)

    assert result is None


def test_parse_lsmem_output_empty(collector):
    """Test parsing of empty lsmem output."""
    result = collector._parse_lsmem_output("")
    assert result is None


def test_parse_numactl_hardware_two_nodes(collector):
    """Test parsing of numactl -H output with 2 NUMA nodes."""
    numactl_output = """available: 2 nodes (0-1)
node 0 cpus: 0 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15
node 0 size: 32768 MB
node 0 free: 15234 MB
node 1 cpus: 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30 31
node 1 size: 32768 MB
node 1 free: 20145 MB
node distances:
node   0   1
  0:  10  21
  1:  21  10"""

    result = collector._parse_numactl_hardware(numactl_output)

    assert result is not None
    assert result.available_nodes == [0, 1]
    assert len(result.nodes) == 2

    # Check node 0
    assert result.nodes[0].node_id == 0
    assert result.nodes[0].cpus == list(range(16))
    assert result.nodes[0].memory_size_mb == 32768
    assert result.nodes[0].memory_free_mb == 15234

    # Check node 1
    assert result.nodes[1].node_id == 1
    assert result.nodes[1].cpus == list(range(16, 32))
    assert result.nodes[1].memory_size_mb == 32768
    assert result.nodes[1].memory_free_mb == 20145

    # Check distances
    assert len(result.distances) == 4
    assert result.distance_matrix is not None
    assert result.distance_matrix[0][0] == 10
    assert result.distance_matrix[0][1] == 21
    assert result.distance_matrix[1][0] == 21
    assert result.distance_matrix[1][1] == 10


def test_parse_numactl_hardware_single_node(collector):
    """Test parsing of numactl -H output with single NUMA node."""
    numactl_output = """available: 1 nodes (0)
node 0 cpus: 0 1 2 3 4 5 6 7
node 0 size: 16384 MB
node 0 free: 8192 MB
node distances:
node   0
  0:  10"""

    result = collector._parse_numactl_hardware(numactl_output)

    assert result is not None
    assert result.available_nodes == [0]
    assert len(result.nodes) == 1
    assert result.nodes[0].node_id == 0
    assert result.nodes[0].cpus == [0, 1, 2, 3, 4, 5, 6, 7]
    assert result.nodes[0].memory_size_mb == 16384
    assert result.nodes[0].memory_free_mb == 8192
    assert len(result.distances) == 1
    assert result.distance_matrix[0][0] == 10


def test_parse_numactl_hardware_no_memory_info(collector):
    """Test parsing of numactl -H output without memory size/free info."""
    numactl_output = """available: 2 nodes (0-1)
node 0 cpus: 0 1 2 3
node 1 cpus: 4 5 6 7
node distances:
node   0   1
  0:  10  21
  1:  21  10"""

    result = collector._parse_numactl_hardware(numactl_output)

    assert result is not None
    assert len(result.nodes) == 2
    assert result.nodes[0].memory_size_mb is None
    assert result.nodes[0].memory_free_mb is None
    assert result.nodes[1].memory_size_mb is None
    assert result.nodes[1].memory_free_mb is None


def test_parse_numactl_hardware_empty_output(collector):
    """Test parsing of empty numactl output."""
    result = collector._parse_numactl_hardware("")
    assert result is None


def test_parse_numactl_hardware_four_nodes(collector):
    """Test parsing of numactl -H output with 4 NUMA nodes."""
    numactl_output = """available: 4 nodes (0-3)
node 0 cpus: 0 1 2 3
node 0 size: 8192 MB
node 0 free: 4096 MB
node 1 cpus: 4 5 6 7
node 1 size: 8192 MB
node 1 free: 3000 MB
node 2 cpus: 8 9 10 11
node 2 size: 8192 MB
node 2 free: 5000 MB
node 3 cpus: 12 13 14 15
node 3 size: 8192 MB
node 3 free: 6000 MB
node distances:
node   0   1   2   3
  0:  10  21  21  21
  1:  21  10  21  21
  2:  21  21  10  21
  3:  21  21  21  10"""

    result = collector._parse_numactl_hardware(numactl_output)

    assert result is not None
    assert result.available_nodes == [0, 1, 2, 3]
    assert len(result.nodes) == 4
    assert len(result.distances) == 16
    assert result.distance_matrix[0][0] == 10
    assert result.distance_matrix[0][3] == 21
    assert result.distance_matrix[3][3] == 10
