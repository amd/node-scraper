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

        def _bytes_to_gb(n: float) -> float:
            return n / (1024**3)

        free_memory = convert_to_bytes(data.mem_free)
        total_memory = convert_to_bytes(data.mem_total)
        used_memory = total_memory - free_memory

        threshold_bytes = convert_to_bytes(args.memory_threshold)

        if total_memory > threshold_bytes:
            base_bytes = threshold_bytes
            base_source = "memory_threshold (max_expected)"
        else:
            base_bytes = total_memory
            base_source = "total_memory"

        max_allowed_used_mem = base_bytes * args.ratio

        used_gb = _bytes_to_gb(used_memory)
        allowed_gb = _bytes_to_gb(max_allowed_used_mem)
        base_gb = _bytes_to_gb(base_bytes)

        if used_memory < max_allowed_used_mem:
            self.result.message = (
                f"Memory usage is within limit: Used {used_gb:.2f} GB "
                f"(allowed {allowed_gb:.2f} GB; base={base_source} {base_gb:.2f} GB × ratio={args.ratio:.2f})"
            )
            self.result.status = ExecutionStatus.OK
        else:
            self.result.message = (
                f"Memory usage exceeded max allowed! Used {used_gb:.2f} GB, "
                f"max allowed {allowed_gb:.2f} GB "
                f"(base={base_source} {base_gb:.2f} GB × ratio={args.ratio:.2f})"
            )
            self.result.status = ExecutionStatus.ERROR
            self._log_event(
                category=EventCategory.OS,
                description=(f"{self.result.message}"),
                priority=EventPriority.CRITICAL,
            )

        return self.result
