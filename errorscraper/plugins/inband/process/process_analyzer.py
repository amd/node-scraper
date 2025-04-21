from typing import Optional

from errorscraper.enums import EventCategory, EventPriority
from errorscraper.interfaces import DataAnalyzer
from errorscraper.models import TaskResult

from .analyzer_args import ProcessAnalyzerArgs
from .processdata import ProcessDataModel


class ProcessAnalyzer(DataAnalyzer[ProcessDataModel, ProcessAnalyzerArgs]):
    """Check cpu and kfd processes are within allowed maximum cpu and gpu usage"""

    DATA_MODEL = ProcessDataModel

    def analyze_data(
        self, data: ProcessDataModel, args: Optional[ProcessAnalyzerArgs] = None
    ) -> TaskResult:
        if not args:
            args = ProcessAnalyzerArgs()

        if data.kfd_process and data.kfd_process > args.max_kfd_processes:
            self._log_event(
                category=EventCategory.OS,
                description="Kfd processes exceeds maximum limit",
                data={
                    "kfd_process": data.kfd_process,
                    "kfd_process_limit": args.max_kfd_processes,
                },
                priority=EventPriority.CRITICAL,
                console_log=True,
            )

        if data.cpu_usage and data.cpu_usage > args.max_cpu_usage:
            self._log_event(
                category=EventCategory.OS,
                description="Kfd processes exceeds maximum limit",
                data={
                    "kfd_process": data.kfd_process,
                    "kfd_process_limit": args.max_kfd_processes,
                },
                priority=EventPriority.CRITICAL,
                console_log=True,
            )

        return self.result
