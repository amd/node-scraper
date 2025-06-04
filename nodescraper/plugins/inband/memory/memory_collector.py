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

from nodescraper.base import InBandDataCollector
from nodescraper.enums import EventCategory, EventPriority, ExecutionStatus, OSFamily
from nodescraper.models import TaskResult

from .memorydata import MemoryDataModel


class MemoryCollector(InBandDataCollector[MemoryDataModel, None]):
    """Collect memory usage details"""

    DATA_MODEL = MemoryDataModel

    def collect_data(self, args=None) -> tuple[TaskResult, MemoryDataModel | None]:
        """
        Collects memory usage details from the system.

        Returns:
            tuple[TaskResult, MemoryDataModel | None]: tuple containing the task result and memory data model or None if data is not available.
        """
        mem_free, mem_total = None, None
        if self.system_info.os_family == OSFamily.WINDOWS:
            os_memory_cmd = self._run_sut_cmd(
                "wmic OS get FreePhysicalMemory /Value; wmic ComputerSystem get TotalPhysicalMemory /Value"
            )
            if os_memory_cmd.exit_code == 0:
                mem_free = re.search(r"FreePhysicalMemory=(\d+)", os_memory_cmd.stdout).group(
                    1
                )  # bytes
                mem_total = re.search(r"TotalPhysicalMemory=(\d+)", os_memory_cmd.stdout).group(1)
        else:
            os_memory_cmd = self._run_sut_cmd("free -b")
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

        if mem_free and mem_total:
            mem_data = MemoryDataModel(mem_free=mem_free, mem_total=mem_total)
            self._log_event(
                category=EventCategory.OS,
                description="Free and total memory read",
                data=mem_data.model_dump(),
                priority=EventPriority.INFO,
            )
            self.result.message = f"Memory: {mem_data.model_dump()}"
            self.result.status = ExecutionStatus.OK
        else:
            mem_data = None
            self.result.message = "Memory usage data not available"
            self.result.status = ExecutionStatus.ERROR

        return self.result, mem_data
