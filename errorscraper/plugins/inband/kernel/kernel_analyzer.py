import re
from typing import Optional

from errorscraper.enums import EventCategory, EventPriority, ExecutionStatus
from errorscraper.interfaces import DataAnalyzer
from errorscraper.models import TaskResult

from .analyzer_args import KernelAnalyzerArgs
from .kerneldata import KernelDataModel


class KernelAnalyzer(DataAnalyzer[KernelDataModel, KernelAnalyzerArgs]):
    """Check kernel matches expected versions"""

    DATA_MODEL = KernelDataModel

    def analyze_data(
        self, data: KernelDataModel, args: Optional[KernelAnalyzerArgs] = None
    ) -> TaskResult:
        if not args:
            self.result.message = "Expected kernel not provided"
            self.result.status = ExecutionStatus.NOT_RAN
            return self.result

        for kernel in args.exp_kernel:
            if args.regex_match:
                try:
                    regex_data = re.compile(kernel)
                except re.error:
                    self._log_event(
                        category=EventCategory.RUNTIME,
                        description="Kernel regex is invalid",
                        data={"regex": kernel},
                        priority=EventPriority.ERROR,
                    )
                    continue
                if regex_data.match(data.kernel_version):
                    self.result.message = "Kernel matches expected"
                    self.result.status = ExecutionStatus.OK
                    return self.result
            elif data.kernel_version == kernel:
                self.result.message = "Kernel matches expected"
                self.result.status = ExecutionStatus.OK
                return self.result

        self.result.message = "Kernel mismatch!"
        self.result.status = ExecutionStatus.ERROR
        self._log_event(
            category=EventCategory.OS,
            description=f"{self.result.message}",
            data={"expected": args.exp_kernel, "actual": data.kernel_version},
            priority=EventPriority.CRITICAL,
            console_log=True,
        )
        return self.result
