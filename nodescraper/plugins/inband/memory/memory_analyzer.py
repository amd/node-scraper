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
from typing import Optional

from nodescraper.enums import EventCategory, EventPriority, ExecutionStatus
from nodescraper.interfaces import DataAnalyzer
from nodescraper.models import TaskResult
from nodescraper.utils import convert_to_bytes

from .analyzer_args import MemoryAnalyzerArgs
from .memorydata import MemoryDataModel


class MemoryAnalyzer(DataAnalyzer[MemoryDataModel, MemoryAnalyzerArgs]):
    """Check memory usage is within the maximum allowed used memory"""

    DATA_MODEL = MemoryDataModel

    def analyze_data(
        self, data: MemoryDataModel, args: Optional[MemoryAnalyzerArgs] = None
    ) -> TaskResult:
        """Analyze the memory data to check if the memory usage is within the maximum allowed used memory.

        Args:
            data (MemoryDataModel): memory data to analyze.
            args (Optional[MemoryAnalyzerArgs], optional): memory analysis arguments. Defaults to None.

        Returns:
            TaskResult: Result of the memory analysis containing the status and message.
        """
        if not args:
            args = MemoryAnalyzerArgs()

        free_memory = convert_to_bytes(data.mem_free)
        total_memory = convert_to_bytes(data.mem_total)
        used_memory = total_memory - free_memory

        if total_memory > convert_to_bytes(args.memory_threshold):
            max_allowed_used_mem = convert_to_bytes(args.memory_threshold) * args.ratio
        else:
            max_allowed_used_mem = total_memory * args.ratio

        if used_memory < max_allowed_used_mem:
            self.result.message = "Memory usage is within maximum allowed used memory"
            self.result.status = ExecutionStatus.OK
        else:
            self.result.message = f"Memory usage exceeded max allowed! Used: {used_memory}, max allowed: {max_allowed_used_mem}"
            self.result.status = ExecutionStatus.ERROR
            self._log_event(
                category=EventCategory.OS,
                description=f"{self.result.message}, Actual: {used_memory}",
                priority=EventPriority.CRITICAL,
                console_log=True,
            )

        return self.result
