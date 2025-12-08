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

from .memorydata import MemoryDataModel


class MemoryCollector(InBandDataCollector[MemoryDataModel, None]):
    """Collect memory usage details"""

    DATA_MODEL = MemoryDataModel

    CMD_WINDOWS = (
        "wmic OS get FreePhysicalMemory /Value; wmic ComputerSystem get TotalPhysicalMemory /Value"
    )
    CMD = "free -b"
    CMD_LSMEM = "/usr/bin/lsmem"

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
                self._log_event(
                    category=EventCategory.OS,
                    description="lsmem output collected",
                    data=lsmem_data,
                    priority=EventPriority.INFO,
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

        if mem_free and mem_total:
            mem_data = MemoryDataModel(
                mem_free=mem_free, mem_total=mem_total, lsmem_output=lsmem_data
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

    def _parse_lsmem_output(self, output: str) -> dict:
        """
        Parse lsmem command output into a structured dictionary.

        Args:
            output: Raw stdout from lsmem command

        Returns:
            dict: Parsed lsmem data with memory blocks and summary information
        """
        lines = output.strip().split("\n")
        memory_blocks = []
        summary = {}

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Parse mem range lines (sample: "0x0000000000000000-0x000000007fffffff   2G online       yes   0-15")
            if line.startswith("0x"):
                parts = line.split()
                if len(parts) >= 4:
                    memory_blocks.append(
                        {
                            "range": parts[0],
                            "size": parts[1],
                            "state": parts[2],
                            "removable": parts[3] if len(parts) > 3 else None,
                            "block": parts[4] if len(parts) > 4 else None,
                        }
                    )
            # Parse summary lines
            elif ":" in line:
                key, value = line.split(":", 1)
                summary[key.strip().lower().replace(" ", "_")] = value.strip()

        return {
            "raw_output": output,
            "memory_blocks": memory_blocks,
            "summary": summary,
        }
