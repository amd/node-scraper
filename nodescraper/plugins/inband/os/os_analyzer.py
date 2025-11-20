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

from .analyzer_args import OsAnalyzerArgs
from .osdata import OsDataModel


class OsAnalyzer(DataAnalyzer[OsDataModel, OsAnalyzerArgs]):
    """Check os matches expected versions"""

    DATA_MODEL = OsDataModel

    def analyze_data(self, data: OsDataModel, args: Optional[OsAnalyzerArgs] = None) -> TaskResult:
        """Analyze the OS data against expected OS names.

        Args:
            data (OsDataModel): Operating System data to analyze.
            args (Optional[OsAnalyzerArgs], optional): OS analysis arguments. Defaults to None.

        Returns:
            TaskResult: Result of the analysis containing status and message.
        """
        if not args or not args.exp_os:
            self.result.message = "Expected OS name not provided"
            self.result.status = ExecutionStatus.NOT_RAN
            return self.result

        for os_name in args.exp_os:
            if (os_name == data.os_name and args.exact_match) or (
                os_name in data.os_name and not args.exact_match
            ):
                self.result.message = "OS name matches expected"
                self.result.status = ExecutionStatus.OK
                return self.result

        self.result.message = f"OS name mismatch! Expected: {args.exp_os}, actual: {data.os_name}"
        self.result.status = ExecutionStatus.ERROR
        self._log_event(
            category=EventCategory.OS,
            description=f"{self.result.message}",
            data={"expected": args.exp_os, "actual": data.os_name},
            priority=EventPriority.CRITICAL,
            console_log=True,
        )
        return self.result
