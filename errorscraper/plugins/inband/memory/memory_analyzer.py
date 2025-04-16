from typing import Optional

from errorscraper.enums import EventCategory, EventPriority, ExecutionStatus
from errorscraper.interfaces import DataAnalyzer
from errorscraper.models import TaskResult
from errorscraper.utils import convert_to_bytes

from .analyzer_args import MemoryAnalyzerArgs
from .memorydata import MemoryDataModel


class MemoryAnalyzer(DataAnalyzer[MemoryDataModel, MemoryAnalyzerArgs]):
    """Check memory usage is within the maximum allowed used memory"""

    DATA_MODEL = MemoryDataModel

    def analyze_data(
        self, data: MemoryDataModel, args: Optional[MemoryAnalyzerArgs] = None
    ) -> TaskResult:
        if not args:
            self.result.message = "Expected memory arg not provided"
            self.result.status = ExecutionStatus.NOT_RAN
            return self.result

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
            self.result.message = "Memory usage is more than the maximum allowed used memory!"
            self.result.status = ExecutionStatus.ERROR
            self._log_event(
                category=EventCategory.OS,
                description=f"{self.result.message}, Actual: {used_memory}",
                priority=EventPriority.CRITICAL,
                console_log=True,
            )

        return self.result
