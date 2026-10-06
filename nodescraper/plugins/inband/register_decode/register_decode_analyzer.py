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
from typing import Optional

from nodescraper.enums import (
    EventCategory,
    EventPriority,
    ExecutionStatus,
    SystemLocation,
)
from nodescraper.interfaces import DataAnalyzer
from nodescraper.models import TaskResult

from .analyzer_args import RegisterDecodeAnalyzerArgs
from .register_decode_data import RegisterDecodeDataModel
from .register_tool import discover_register_tool


class RegisterDecodeAnalyzer(DataAnalyzer[RegisterDecodeDataModel, RegisterDecodeAnalyzerArgs]):
    """Decode collected register records through an installed register-tool entry point."""

    DATA_MODEL = RegisterDecodeDataModel

    def analyze_data(
        self,
        data: RegisterDecodeDataModel,
        args: Optional[RegisterDecodeAnalyzerArgs] = None,
    ) -> TaskResult:
        """Decode collected register records with the discovered register tool.

        Args:
            data: Collected stats and register records.
            args: Analyzer arguments for tool selection.

        Returns:
            Task result for the decode.
        """
        if args is None:
            args = RegisterDecodeAnalyzerArgs()
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
        try:
            tool = discover_register_tool(name=args.tool_name, group=args.tool_group)
            if callable(getattr(tool, "record_from_row", None)):
                records = [tool.record_from_row(row) for row in data.records]
            else:
                records = list(data.records)
            decoded_collection = tool.decode_records(records)
            decoded = decoded_collection.model_dump(mode="json")
        except Exception as exc:
            return self._fail(f"Register decode failed: {exc}")

        count = len(decoded["records"])
        self.result.status = ExecutionStatus.OK
        self.result.message = f"Decoded {count} register record(s)"
        self._log_event(
            category=EventCategory.RAS,
            description=self.result.message,
            data=decoded,
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
