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
from __future__ import annotations

from typing import Any, Optional

from nodescraper.base import RedfishDataCollector
from nodescraper.enums import ExecutionStatus
from nodescraper.models import TaskResult
from nodescraper.plugins.serviceability.time_utils import satisfies_time_check

from .oob_redfish_collector_args import OobRedfishCollectorArgs
from .oob_redfish_data import OobRedfishDataModel


class OobRedfishCollector(
    RedfishDataCollector[OobRedfishDataModel, OobRedfishCollectorArgs],
):
    """Collect OOB Redfish serviceability data."""

    DATA_MODEL = OobRedfishDataModel

    def __init__(self, **kwargs: Any) -> None:
        self._log_path: Optional[str] = kwargs.pop("log_path", None)
        super().__init__(**kwargs)

    def satisfies_reference_time(
        self,
        candidate: str,
        args: OobRedfishCollectorArgs,
    ) -> bool:
        """Test a timestamp against optional reference-time filter settings.

        Args:
            candidate: Timestamp string to test.
            args: Collector arguments that may define reference_time and time_operator.

        Returns:
            True when no filter is configured or the comparison succeeds.
        """
        if args.reference_time is None or args.time_operator is None:
            return True
        return satisfies_time_check(candidate, args.reference_time, args.time_operator)

    def _missing_args_result(self) -> tuple[TaskResult, None]:
        """Build a not-ran result when collector arguments are missing.

        Returns:
            Task result with NOT_RAN status and no data model.
        """
        self.result.status = ExecutionStatus.NOT_RAN
        self.result.message = "OobRedfishCollectorArgs are required"
        return self.result, None
