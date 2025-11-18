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

from nodescraper.enums import EventCategory, EventPriority, ExecutionStatus
from nodescraper.interfaces import DataAnalyzer
from nodescraper.models import TaskResult

from .analyzer_args import KernelAnalyzerArgs
from .kerneldata import KernelDataModel


class KernelAnalyzer(DataAnalyzer[KernelDataModel, KernelAnalyzerArgs]):
    """Check kernel matches expected versions"""

    DATA_MODEL = KernelDataModel

    def analyze_data(
        self, data: KernelDataModel, args: Optional[KernelAnalyzerArgs] = None
    ) -> TaskResult:
        """Analyze the kernel data against expected versions.

        Args:
            data (KernelDataModel): Kernel data to analyze.
            args (Optional[KernelAnalyzerArgs], optional): Kernel analysis arguments. Defaults to None.

        Returns:
            TaskResult: Result of the analysis containing status and message.
        """
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

        self.result.message = (
            f"Kernel mismatch! Expected: {args.exp_kernel}, actual: {data.kernel_version}"
        )
        self.result.status = ExecutionStatus.ERROR
        self._log_event(
            category=EventCategory.OS,
            description=f"{self.result.message}",
            data={"expected": args.exp_kernel, "actual": data.kernel_version},
            priority=EventPriority.CRITICAL,
            console_log=True,
        )
        return self.result
