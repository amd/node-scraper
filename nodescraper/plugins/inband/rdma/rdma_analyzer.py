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

from nodescraper.enums import EventCategory, EventPriority, ExecutionStatus
from nodescraper.interfaces import DataAnalyzer
from nodescraper.models import TaskResult

from .rdmadata import RdmaDataModel


class RdmaAnalyzer(DataAnalyzer[RdmaDataModel, None]):
    """Check RDMA statistics for errors (RoCE and other RDMA error counters)."""

    DATA_MODEL = RdmaDataModel

    def analyze_data(self, data: RdmaDataModel, args: Optional[None] = None) -> TaskResult:
        """Analyze RDMA statistics for non-zero error counters.

        Error and critical counter names come from each vendor's statistics model
        (ionic / bnxt / mlx prefixes).

        Args:
            data: RDMA data model with statistic_list (and optionally link_list).
            args: Unused (analyzer has no configurable args).

        Returns:
            TaskResult with status OK if no errors, ERROR if any error counter > 0.
        """
        if not data.statistic_list:
            self.result.message = "No RDMA devices found"
            self.result.status = ExecutionStatus.WARNING
            return self.result

        error_state = False

        for stat in data.statistic_list:
            if stat.vendor_statistics is None:
                continue

            error_fields = stat.vendor_statistics.error_fields
            critical_fields = stat.vendor_statistics.critial_error_fields

            for error_field in error_fields + critical_fields:
                error_value = getattr(stat.vendor_statistics, error_field, None)

                if error_value is not None and error_value > 0:
                    priority = (
                        EventPriority.CRITICAL
                        if error_field in critical_fields
                        else EventPriority.ERROR
                    )
                    self._log_event(
                        category=EventCategory.NETWORK,
                        description=f"RDMA error detected: {error_field}",
                        data={
                            "interface": stat.ifname,
                            "port": stat.port,
                            "error_field": error_field,
                            "error_count": error_value,
                        },
                        priority=priority,
                        console_log=True,
                    )
                    error_state = True

        if error_state:
            self.result.message = "RDMA errors detected in statistics"
            self.result.status = ExecutionStatus.ERROR
        else:
            self.result.message = "No RDMA errors detected in statistics"
            self.result.status = ExecutionStatus.OK
        return self.result
