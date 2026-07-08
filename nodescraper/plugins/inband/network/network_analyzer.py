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

from nodescraper.base.regexanalyzer import ErrorRegex, RegexAnalyzer
from nodescraper.enums import EventCategory, EventPriority, ExecutionStatus
from nodescraper.models import TaskResult

from .analyzer_args import NetworkAnalyzerArgs
from .networkdata import NetworkDataModel


class NetworkAnalyzer(RegexAnalyzer[NetworkDataModel, NetworkAnalyzerArgs]):
    """Check network statistics for errors."""

    DATA_MODEL = NetworkDataModel

    # No built-in regex patterns: RDMA-scoped counter classification lives in the vendor
    # ethtool models (ethtool_vendor.py). This list is only extended by user-supplied
    # NetworkAnalyzerArgs.error_regex patterns.
    ERROR_REGEX: list[ErrorRegex] = []

    def analyze_data(
        self, data: NetworkDataModel, args: Optional[NetworkAnalyzerArgs] = None
    ) -> TaskResult:
        """Analyze ethtool -S statistics via RDMA-scoped vendor models and any user-supplied regex.

        Args:
            data: Network data model with ethtool_info and/or rdma_ethtool_statistics.
            args: Optional analyzer arguments with custom error regex support.

        Returns:
            TaskResult with OK, WARNING (no devices, or only warning-tier counters), or ERROR.
        """
        if not data.ethtool_info and not data.rdma_ethtool_statistics:
            self.result.message = "No network devices found"
            self.result.status = ExecutionStatus.WARNING
            return self.result

        if not args:
            args = NetworkAnalyzerArgs()

        final_error_regex = self._convert_and_extend_error_regex(args.error_regex, self.ERROR_REGEX)

        regex_error = False
        regex_warning = False
        for interface_name, ethtool_info in data.ethtool_info.items():
            matches_on_interface: list[tuple[str, int, EventPriority]] = []
            for stat_name, stat_value in ethtool_info.statistics.items():
                for error_regex_obj in final_error_regex:
                    if error_regex_obj.regex.match(stat_name):
                        try:
                            value = int(stat_value)
                        except (ValueError, TypeError):
                            break

                        if value > 0:
                            matches_on_interface.append(
                                (stat_name, value, error_regex_obj.event_priority)
                            )
                        break

            if matches_on_interface:
                has_error = any(
                    priority == EventPriority.ERROR for _, _, priority in matches_on_interface
                )
                if has_error:
                    regex_error = True
                else:
                    regex_warning = True
                priority = EventPriority.ERROR if has_error else EventPriority.WARNING
                severity = "error" if has_error else "warning"
                match_names = [match[0] for match in matches_on_interface]
                matches_data = {name: value for name, value, _ in matches_on_interface}
                self._log_event(
                    category=EventCategory.NETWORK,
                    description=f"Network {severity} detected on {interface_name}: [{', '.join(match_names)}]",
                    data={
                        "interface": interface_name,
                        "errors": matches_data,
                    },
                    priority=priority,
                    console_log=True,
                )

        vendor_error = False
        vendor_warning = False
        vendor_error_fields: set[str] = set()
        vendor_warning_fields: set[str] = set()
        for stat in data.rdma_ethtool_statistics:
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
                    # Use a single grouped description per severity so the run summary
                    # collapses every occurrence into one "Ethtool warning detected" /
                    # "Ethtool error detected" entry instead of one line per field. The
                    # specific field is still preserved in the event data below and in
                    # the consolidated console line emitted after the loop.
                    desc = (
                        "Ethtool warning detected" if is_warning_tier else "Ethtool error detected"
                    )
                    # Per-field events are still recorded for the run summary and event
                    # log, but console logging is suppressed here to avoid repeating the
                    # same message once per device. A single consolidated line is emitted
                    # after the loop instead.
                    self._log_event(
                        category=EventCategory.NETWORK,
                        description=desc,
                        data={
                            "netdev": stat.netdev,
                            "rdma_ifname": stat.rdma_ifname,
                            "error_field": field_name,
                            "error_count": error_value,
                        },
                        priority=priority,
                        console_log=False,
                    )

        if vendor_error:
            self.logger.error("Ethtool error detected: %s", ", ".join(sorted(vendor_error_fields)))
        if vendor_warning:
            self.logger.warning(
                "Ethtool warning detected: %s", ", ".join(sorted(vendor_warning_fields))
            )

        if regex_error or vendor_error:
            self.result.message = "Network errors detected in statistics"
            self.result.status = ExecutionStatus.ERROR
        elif regex_warning or vendor_warning:
            self.result.message = "Network warning counters non-zero in statistics"
            self.result.status = ExecutionStatus.WARNING
        else:
            self.result.message = "No network errors detected in statistics"
            self.result.status = ExecutionStatus.OK

        return self.result
