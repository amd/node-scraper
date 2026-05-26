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

from nodescraper.base.regexanalyzer import ErrorRegex, RegexAnalyzer
from nodescraper.enums import EventCategory, EventPriority, ExecutionStatus
from nodescraper.models import TaskResult

from .analyzer_args import NetworkAnalyzerArgs
from .networkdata import NetworkDataModel


class NetworkAnalyzer(RegexAnalyzer[NetworkDataModel, NetworkAnalyzerArgs]):
    """Check network statistics for errors (PFC and other network error counters)."""

    DATA_MODEL = NetworkDataModel

    # Regex patterns for error fields checked from network statistics
    ERROR_REGEX: list[ErrorRegex] = [
        ErrorRegex(
            regex=re.compile(r"^tx_pfc_frames$"),
            message="tx_pfc_frames is non-zero",
            event_category=EventCategory.NETWORK,
        ),
        ErrorRegex(
            regex=re.compile(r"^tx_pfc_ena_frames_pri\d+$"),
            message="tx_pfc_ena_frames_pri* is non-zero",
            event_category=EventCategory.NETWORK,
        ),
        ErrorRegex(
            regex=re.compile(r"^pfc_pri\d+_tx_transitions$"),
            message="pfc_pri*_tx_transitions is non-zero",
            event_category=EventCategory.NETWORK,
        ),
    ]

    def analyze_data(
        self, data: NetworkDataModel, args: Optional[NetworkAnalyzerArgs] = None
    ) -> TaskResult:
        """Analyze ethtool -S statistics: regex-based (per interface) and vendor-based (RDMA-scoped).

        Args:
            data: Network data model with ethtool_info and/or rdma_ethtool_statistics.
            args: Optional analyzer arguments with custom error regex support.

        Returns:
            TaskResult with OK, WARNING (no data or vendor warning counters only), or ERROR.
        """
        if not data.ethtool_info and not data.rdma_ethtool_statistics:
            self.result.message = "No network devices found"
            self.result.status = ExecutionStatus.WARNING
            return self.result

        if not args:
            args = NetworkAnalyzerArgs()

        final_error_regex = self._convert_and_extend_error_regex(args.error_regex, self.ERROR_REGEX)

        regex_error = False
        for interface_name, ethtool_info in data.ethtool_info.items():
            errors_on_interface: list[tuple[str, int]] = []
            for stat_name, stat_value in ethtool_info.statistics.items():
                for error_regex_obj in final_error_regex:
                    if error_regex_obj.regex.match(stat_name):
                        try:
                            value = int(stat_value)
                        except (ValueError, TypeError):
                            break

                        if value > 0:
                            errors_on_interface.append((stat_name, value))
                        break

            if errors_on_interface:
                regex_error = True
                error_names = [e[0] for e in errors_on_interface]
                errors_data = {field: value for field, value in errors_on_interface}
                self._log_event(
                    category=EventCategory.NETWORK,
                    description=f"Network error detected on {interface_name}: [{', '.join(error_names)}]",
                    data={
                        "interface": interface_name,
                        "errors": errors_data,
                    },
                    priority=EventPriority.ERROR,
                    console_log=True,
                )

        vendor_error = False
        vendor_warning = False
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
                    else:
                        vendor_error = True
                    desc = (
                        f"Ethtool warning detected: {field_name}"
                        if is_warning_tier
                        else f"Ethtool error detected: {field_name}"
                    )
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
                        console_log=True,
                    )

        if regex_error or vendor_error:
            self.result.message = "Network errors detected in statistics"
            self.result.status = ExecutionStatus.ERROR
        elif vendor_warning:
            self.result.message = "Network vendor ethtool warning counters non-zero"
            self.result.status = ExecutionStatus.WARNING
        else:
            self.result.message = "No network errors detected in statistics"
            self.result.status = ExecutionStatus.OK
        return self.result
