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
import re
from typing import Optional

from nodescraper.base import InBandDataCollector
from nodescraper.enums import EventCategory, EventPriority, ExecutionStatus, OSFamily
from nodescraper.models import TaskResult

from .memorydata import (
    LsmemData,
    MemoryBlock,
    MemoryDataModel,
    MemorySummary,
    NumaDistance,
    NumaNode,
    NumaTopology,
)


class MemoryCollector(InBandDataCollector[MemoryDataModel, None]):
    """Collect memory usage details"""

    DATA_MODEL = MemoryDataModel

    CMD_WINDOWS = (
        "wmic OS get FreePhysicalMemory /Value; wmic ComputerSystem get TotalPhysicalMemory /Value"
    )
    CMD = "free -b"
    CMD_LSMEM = "lsmem"
    CMD_NUMACTL = "numactl -H"

    def collect_data(self, args=None) -> tuple[TaskResult, Optional[MemoryDataModel]]:
        """
        Collects memory usage details from the system.

        Returns:
            tuple[TaskResult, Optional[MemoryDataModel]]: tuple containing the task result and memory data model or None if data is not available.
        """
        mem_free, mem_total = None, None
        if self.system_info.os_family == OSFamily.WINDOWS:
            os_memory_cmd = self._run_sut_cmd(self.CMD_WINDOWS)
            if os_memory_cmd.exit_code == 0:
                mem_free = re.search(r"FreePhysicalMemory=(\d+)", os_memory_cmd.stdout).group(
                    1
                )  # bytes
                mem_total = re.search(r"TotalPhysicalMemory=(\d+)", os_memory_cmd.stdout).group(1)
        else:
            os_memory_cmd = self._run_sut_cmd(self.CMD)
            if os_memory_cmd.exit_code == 0:
                pattern = r"Mem:\s+(\d\.?\d*\w+)\s+\d\.?\d*\w+\s+(\d\.?\d*\w+)"
                mem_free = re.search(pattern, os_memory_cmd.stdout).group(2)
                mem_total = re.search(pattern, os_memory_cmd.stdout).group(1)

        if os_memory_cmd.exit_code != 0:
            self._log_event(
                category=EventCategory.OS,
                description="Error checking available and total memory",
                data={
                    "command": os_memory_cmd.command,
                    "exit_code": os_memory_cmd.exit_code,
                    "stderr": os_memory_cmd.stderr,
                },
                priority=EventPriority.ERROR,
                console_log=True,
            )

        lsmem_data = None
        if self.system_info.os_family != OSFamily.WINDOWS:
            lsmem_cmd = self._run_sut_cmd(self.CMD_LSMEM)
            if lsmem_cmd.exit_code == 0:
                lsmem_data = self._parse_lsmem_output(lsmem_cmd.stdout)
                if lsmem_data:
                    self._log_event(
                        category=EventCategory.OS,
                        description="lsmem output collected",
                        data={
                            "memory_blocks": len(lsmem_data.memory_blocks),
                            "total_online_memory": lsmem_data.summary.total_online_memory,
                        },
                        priority=EventPriority.INFO,
                    )
                else:
                    self._log_event(
                        category=EventCategory.OS,
                        description="Failed to parse lsmem output",
                        priority=EventPriority.WARNING,
                        console_log=False,
                    )
            else:
                self._log_event(
                    category=EventCategory.OS,
                    description="Error running lsmem command",
                    data={
                        "command": lsmem_cmd.command,
                        "exit_code": lsmem_cmd.exit_code,
                        "stderr": lsmem_cmd.stderr,
                    },
                    priority=EventPriority.WARNING,
                    console_log=False,
                )

        # Collect NUMA topology information
        numa_topology = None
        if self.system_info.os_family != OSFamily.WINDOWS:
            numactl_cmd = self._run_sut_cmd(self.CMD_NUMACTL)
            if numactl_cmd.exit_code == 0:
                numa_topology = self._parse_numactl_hardware(numactl_cmd.stdout)
                if numa_topology:
                    self._log_event(
                        category=EventCategory.MEMORY,
                        description="NUMA topology collected",
                        data={
                            "available_nodes": numa_topology.available_nodes,
                            "node_count": len(numa_topology.nodes),
                        },
                        priority=EventPriority.INFO,
                    )
                else:
                    self._log_event(
                        category=EventCategory.MEMORY,
                        description="Failed to parse numactl output",
                        priority=EventPriority.WARNING,
                        console_log=False,
                    )
            else:
                self._log_event(
                    category=EventCategory.MEMORY,
                    description="Error running numactl command",
                    data={
                        "command": numactl_cmd.command,
                        "exit_code": numactl_cmd.exit_code,
                        "stderr": numactl_cmd.stderr,
                    },
                    priority=EventPriority.WARNING,
                    console_log=False,
                )

        if mem_free and mem_total:
            mem_data = MemoryDataModel(
                mem_free=mem_free,
                mem_total=mem_total,
                lsmem_data=lsmem_data,
                numa_topology=numa_topology,
            )
            self._log_event(
                category=EventCategory.OS,
                description="Free and total memory read",
                data=mem_data.model_dump(),
                priority=EventPriority.INFO,
            )
            self.result.message = f"Memory: mem_free={mem_free}, mem_total={mem_total}"
            self.result.status = ExecutionStatus.OK
        else:
            mem_data = None
            self.result.message = "Memory usage data not available"
            self.result.status = ExecutionStatus.ERROR

        return self.result, mem_data

    def _parse_lsmem_output(self, output: str):
        """
        Parse lsmem command output into a structured LsmemData object.

        Args:
            output: Raw stdout from lsmem command

        Returns:
            LsmemData: Parsed lsmem data with memory blocks and summary information
        """
        lines = output.strip().split("\n")
        memory_blocks = []
        summary_dict = {}

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Parse mem range lines (sample: "0x0000000000000000-0x000000007fffffff   2G online       yes   0-15")
            if line.startswith("0x"):
                parts = line.split()
                if len(parts) >= 4:
                    memory_blocks.append(
                        MemoryBlock(
                            range=parts[0],
                            size=parts[1],
                            state=parts[2],
                            removable=parts[3] if len(parts) > 3 else None,
                            block=parts[4] if len(parts) > 4 else None,
                        )
                    )
            # Parse summary lines
            elif ":" in line:
                key, value = line.split(":", 1)
                summary_dict[key.strip().lower().replace(" ", "_")] = value.strip()

        summary = MemorySummary(
            memory_block_size=summary_dict.get("memory_block_size"),
            total_online_memory=summary_dict.get("total_online_memory"),
            total_offline_memory=summary_dict.get("total_offline_memory"),
        )

        if not memory_blocks:
            return None

        return LsmemData(memory_blocks=memory_blocks, summary=summary)

    def _parse_numactl_hardware(self, output: str):
        """
        Parse 'numactl -H' output into NumaTopology structure.

        Args:
            output: Raw stdout from numactl -H command

        Returns:
            NumaTopology object or None if parsing fails
        """
        lines = output.strip().split("\n")
        available_nodes = []
        nodes = []
        distances = []
        distance_matrix = {}

        current_section = None

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Parse available nodes line
            if line.startswith("available:"):
                match = re.search(r"available:\s*(\d+)\s+nodes?\s*\(([^)]+)\)", line)
                if match:
                    node_range = match.group(2)
                    if "-" in node_range:
                        start, end = node_range.split("-")
                        available_nodes = list(range(int(start), int(end) + 1))
                    else:
                        available_nodes = [int(x.strip()) for x in node_range.split()]

            # Parse node CPU line
            elif line.startswith("node") and "cpus:" in line:
                match = re.search(r"node\s+(\d+)\s+cpus:\s*(.+)", line)
                if match:
                    node_id = int(match.group(1))
                    cpu_list_str = match.group(2).strip()
                    if cpu_list_str:
                        cpus = [int(x) for x in cpu_list_str.split()]
                    else:
                        cpus = []
                    nodes.append(NumaNode(node_id=node_id, cpus=cpus))

            # Parse node memory size
            elif line.startswith("node") and "size:" in line:
                match = re.search(r"node\s+(\d+)\s+size:\s*(\d+)\s*MB", line)
                if match:
                    node_id = int(match.group(1))
                    size_mb = int(match.group(2))
                    # Find existing node and update
                    for node in nodes:
                        if node.node_id == node_id:
                            node.memory_size_mb = size_mb
                            break

            # Parse node free memory
            elif line.startswith("node") and "free:" in line:
                match = re.search(r"node\s+(\d+)\s+free:\s*(\d+)\s*MB", line)
                if match:
                    node_id = int(match.group(1))
                    free_mb = int(match.group(2))
                    # Find existing node and update
                    for node in nodes:
                        if node.node_id == node_id:
                            node.memory_free_mb = free_mb
                            break

            # Parse distance matrix
            elif line.startswith("node distances:"):
                current_section = "distances"

            elif current_section == "distances":
                if line.startswith("node") and ":" not in line:
                    continue
                elif ":" in line:
                    parts = line.split(":")
                    if len(parts) == 2:
                        from_node = int(parts[0].strip())
                        dist_values = [int(x) for x in parts[1].split()]

                        distance_matrix[from_node] = {}
                        for to_node, dist in enumerate(dist_values):
                            distance_matrix[from_node][to_node] = dist
                            distances.append(
                                NumaDistance(from_node=from_node, to_node=to_node, distance=dist)
                            )

        if not nodes:
            return None

        return NumaTopology(
            available_nodes=available_nodes if available_nodes else [n.node_id for n in nodes],
            nodes=nodes,
            distances=distances,
            distance_matrix=distance_matrix if distance_matrix else None,
        )
