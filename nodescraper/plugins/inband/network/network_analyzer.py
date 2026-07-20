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

from nodescraper.base.regexanalyzer import RegexAnalyzer
from nodescraper.enums import EventCategory, EventPriority, ExecutionStatus
from nodescraper.models import TaskResult

from .networkdata import NetworkDataModel


class NetworkAnalyzer(RegexAnalyzer[NetworkDataModel, None]):
    """Check network statistics for errors."""

    DATA_MODEL = NetworkDataModel

    def analyze_data(self, data: NetworkDataModel, args=None) -> TaskResult:
        """Analyze ethtool -S statistics via RDMA-scoped vendor models.

        Args:
            data: Network data model with ethtool_statistics.
            args: Unused; retained for analyzer interface compatibility.

        Returns:
            TaskResult with OK, WARNING (no devices, or only warning-tier counters), or ERROR.
        """
        if not data.ethtool_info and not data.ethtool_statistics:
            self.result.message = "No network devices found"
            self.result.status = ExecutionStatus.WARNING
            return self.result

        vendor_error = False
        vendor_warning = False
        vendor_error_fields: set[str] = set()
        vendor_warning_fields: set[str] = set()
        vendor_queue_error_fields: set[str] = set()
        vendor_queue_warning_fields: set[str] = set()
        for stat in data.ethtool_statistics:
            if stat.vendor_statistics is None:
                continue

            vs = stat.vendor_statistics
            error_fields = vs.error_fields
            warning_fields = vs.warning_fields

            for field_name in error_fields + warning_fields:
                error_value = getattr(vs, field_name, None)
                if error_value is not None and error_value > 0:
                    is_warning_tier = field_name in warning_fields
                    priority = EventPriority.WARNING if is_warning_tier else EventPriority.ERROR
                    if is_warning_tier:
                        vendor_warning = True
                        vendor_warning_fields.add(field_name)
                    else:
                        vendor_error = True
                        vendor_error_fields.add(field_name)
                    # Use a single grouped description per severity
                    desc = (
                        "Ethtool warning detected" if is_warning_tier else "Ethtool error detected"
                    )
                    # Per-field events are still recorded for the run summary and event
                    # log, but console logging is suppressed here
                    self._log_event(
                        category=EventCategory.NETWORK,
                        description=desc,
                        data={
                            "netdev": stat.netdev,
                            "driver": stat.driver,
                            "error_field": field_name,
                            "error_count": error_value,
                        },
                        priority=priority,
                        console_log=False,
                    )

            # Per-queue counters matched against the vendor's adjustable regex
            queue_error_patterns = [
                re.compile(pattern) for pattern in getattr(type(vs), "queue_error_regex", [])
            ]
            queue_warning_patterns = [
                re.compile(pattern) for pattern in getattr(type(vs), "queue_warning_regex", [])
            ]
            if stat.queue_statistics and (queue_error_patterns or queue_warning_patterns):
                for counter_name, counter_value in stat.queue_statistics.items():
                    if counter_value <= 0:
                        continue
                    if queue_error_patterns and any(
                        pattern.search(counter_name) for pattern in queue_error_patterns
                    ):
                        vendor_error = True
                        vendor_queue_error_fields.add(f"{stat.netdev} {counter_name}")
                        self._log_event(
                            category=EventCategory.NETWORK,
                            description="Ethtool queue error detected",
                            data={
                                "netdev": stat.netdev,
                                "driver": stat.driver,
                                "error_field": counter_name,
                                "error_count": counter_value,
                            },
                            priority=EventPriority.ERROR,
                            console_log=False,
                        )
                    elif queue_warning_patterns and any(
                        pattern.search(counter_name) for pattern in queue_warning_patterns
                    ):
                        vendor_warning = True
                        vendor_queue_warning_fields.add(f"{stat.netdev} {counter_name}")
                        self._log_event(
                            category=EventCategory.NETWORK,
                            description="Ethtool queue warning detected",
                            data={
                                "netdev": stat.netdev,
                                "driver": stat.driver,
                                "error_field": counter_name,
                                "error_count": counter_value,
                            },
                            priority=EventPriority.WARNING,
                            console_log=False,
                        )

        if vendor_error_fields:
            self.logger.error("Ethtool error detected: %s", ", ".join(sorted(vendor_error_fields)))
        if vendor_queue_error_fields:
            self.logger.error(
                "Ethtool queue error detected: %s",
                ", ".join(sorted(vendor_queue_error_fields)),
            )
        if vendor_warning_fields:
            self.logger.warning(
                "Ethtool warning detected: %s", ", ".join(sorted(vendor_warning_fields))
            )
        if vendor_queue_warning_fields:
            self.logger.warning(
                "Ethtool queue warning detected: %s",
                ", ".join(sorted(vendor_queue_warning_fields)),
            )

        if vendor_error:
            self.result.message = "Network errors detected in statistics"
            self.result.status = ExecutionStatus.ERROR
        elif vendor_warning:
            self.result.message = "Network warning counters non-zero in statistics"
            self.result.status = ExecutionStatus.WARNING
        else:
            self.result.message = "No network errors detected in statistics"
            self.result.status = ExecutionStatus.OK

        return self.result
