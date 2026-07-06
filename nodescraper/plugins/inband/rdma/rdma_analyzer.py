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
import re
from typing import Optional

from nodescraper.enums import EventCategory, EventPriority, ExecutionStatus
from nodescraper.interfaces import DataAnalyzer
from nodescraper.models import TaskResult

from .analyzer_args import RdmaAnalyzerArgs
from .rdmadata import RdmaDataModel


class RdmaAnalyzer(DataAnalyzer[RdmaDataModel, RdmaAnalyzerArgs]):
    """Check RDMA statistics for errors (RoCE and other RDMA error counters)."""

    DATA_MODEL = RdmaDataModel

    def analyze_data(
        self, data: RdmaDataModel, args: Optional[RdmaAnalyzerArgs] = None
    ) -> TaskResult:
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

        if not args:
            args = RdmaAnalyzerArgs()

        compiled_exclusions = [re.compile(pattern) for pattern in (args.exclusion_regex or [])]

        error_detected = False
        critical_detected = False
        error_fields_seen: set[str] = set()
        critical_fields_seen: set[str] = set()
        skipped_count = 0

        for stat in data.statistic_list:
            # Skip this interface if its netdev matches any exclusion regex
            if stat.netdev and any(pattern.search(stat.netdev) for pattern in compiled_exclusions):
                skipped_count += 1
                continue

            if stat.vendor_statistics is None:
                continue

            error_fields = stat.vendor_statistics.error_fields
            critical_fields = stat.vendor_statistics.critical_error_fields

            detected_errors: dict[str, int] = {}
            has_critical = False
            for error_field in error_fields + critical_fields:
                error_value = getattr(stat.vendor_statistics, error_field, None)
                if error_value is not None and error_value > 0:
                    detected_errors[error_field] = error_value
                    if error_field in critical_fields:
                        has_critical = True
                        critical_detected = True
                        critical_fields_seen.add(error_field)
                    else:
                        error_detected = True
                        error_fields_seen.add(error_field)

            if not detected_errors:
                continue

            priority = EventPriority.CRITICAL if has_critical else EventPriority.ERROR
            desc = "RDMA critical error detected" if has_critical else "RDMA error detected"
            self._log_event(
                category=EventCategory.NETWORK,
                description=desc,
                data={
                    "netdev": stat.netdev,
                    "interface": stat.ifname,
                    "port": stat.port,
                    "errors": detected_errors,
                },
                priority=priority,
                console_log=False,
            )

        if critical_detected:
            self.logger.critical(
                "RDMA critical error detected: %s", ", ".join(sorted(critical_fields_seen))
            )
        if error_detected:
            self.logger.error("RDMA error detected: %s", ", ".join(sorted(error_fields_seen)))

        if error_detected or critical_detected:
            self.result.message = "RDMA errors detected in statistics"
            self.result.status = ExecutionStatus.ERROR
        else:
            self.result.message = "No RDMA errors detected in statistics"
            self.result.status = ExecutionStatus.OK

        if skipped_count:
            self.result.message += f" ({skipped_count} skipped)"

        return self.result
