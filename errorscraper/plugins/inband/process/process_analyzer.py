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
        """
        Analyze the process data to check if the number of KFD processes and CPU usage
        are within the allowed limits.

        Args:
            data (ProcessDataModel): The process data to analyze.
            args (Optional[ProcessAnalyzerArgs], optional): The process analysis arguments. Defaults to None.

        Returns:
            TaskResult: The result of the analysis, containing any events logged during the process.
        """
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
