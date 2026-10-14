###############################################################################
#
# MIT License
#
# Copyright (c) 2026 Advanced Micro Devices, Inc.
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
from nodescraper.enums import (
    EventCategory,
    EventPriority,
    ExecutionStatus,
    SystemLocation,
)
from nodescraper.interfaces import DataAnalyzer
from nodescraper.models import TaskResult

from .register_decode_data import RegisterDecodeDataModel


class RegisterDecodeAnalyzer(DataAnalyzer[RegisterDecodeDataModel, None]):
    """Report register records already decoded on the data model."""

    DATA_MODEL = RegisterDecodeDataModel

    def analyze_data(self, data: RegisterDecodeDataModel, args=None) -> TaskResult:
        """Report decoded register records.

        Args:
            data: Collected stats and register records.
            args: Analysis arguments. Defaults to None.

        Returns:
            Task result for the decoded records.
        """
        if data.decoded_records is not None:
            return self._report_decoded(data)
        if self.system_info.location == SystemLocation.REMOTE:
            message = "Register decode is only supported on local"
            self.result.status = ExecutionStatus.NOT_RAN
            self.result.message = message
            self._log_event(
                category=EventCategory.RAS,
                description=message,
                priority=EventPriority.INFO,
                console_log=True,
            )
            return self.result
        return self._fail("Register records were not decoded")

    def _report_decoded(self, data: RegisterDecodeDataModel) -> TaskResult:
        """Report records already decoded on the data model.

        Args:
            data: Collected records plus decoded results.

        Returns:
            Task result for the decode.
        """
        decoded = list(data.decoded_records or [])
        self.result.status = ExecutionStatus.OK
        self.result.message = f"Decoded {len(decoded)} register record(s)"
        self._log_event(
            category=EventCategory.RAS,
            description=self.result.message,
            data={"records": decoded},
            priority=EventPriority.INFO,
        )
        return self.result

    def _fail(self, message: str) -> TaskResult:
        """Record a decode failure.

        Args:
            message: Failure text stored on the task result.

        Returns:
            The failed task result.
        """
        self.result.status = ExecutionStatus.ERROR
        self.result.message = message
        self._log_event(
            category=EventCategory.RAS,
            description=message,
            priority=EventPriority.ERROR,
            console_log=True,
        )
        return self.result
