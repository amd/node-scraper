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

from .networkdata import NetworkDataModel


class NetworkAnalyzer(DataAnalyzer[NetworkDataModel, None]):
    """Check network statistics for errors (PFC and other network error counters)."""

    DATA_MODEL = NetworkDataModel

    # Regex patterns for error fields checked from network statistics
    ERROR_FIELD_PATTERNS = [
        r"^tx_pfc_frames$",
        r"^tx_pfc_ena_frames_pri\d+$",
        r"^pfc_pri\d+_tx_transitions$",
    ]

    def analyze_data(self, data: NetworkDataModel, args: Optional[None] = None) -> TaskResult:
        """Analyze network statistics for non-zero error counters.
        Currently only checks ethtool -S statistics.

        Args:
            data: Network data model with ethtool_info containing interface statistics.
            args: Unused (analyzer has no configurable args).

        Returns:
            TaskResult with status OK if no errors, ERROR if any error counter > 0.
        """
        if not data.ethtool_info:
            self.result.message = "No network devices found"
            self.result.status = ExecutionStatus.WARNING
            return self.result

        error_state = False
        for interface_name, ethtool_info in data.ethtool_info.items():
            errors_on_interface = []  # (error_field, value)
            # Loop through all statistics in the ethtool statistics dict
            for stat_name, stat_value in ethtool_info.statistics.items():
                # Check if this statistic matches any error field pattern
                for pattern in self.ERROR_FIELD_PATTERNS:
                    if re.match(pattern, stat_name):
                        # Try to convert string value to int
                        try:
                            value = int(stat_value)
                        except (ValueError, TypeError):
                            break  # Skip non-numeric values

                        if value > 0:
                            errors_on_interface.append((stat_name, value))
                        break  # Stop checking patterns once we find a match

            if errors_on_interface:
                error_state = True
                error_names = [e[0] for e in errors_on_interface]
                errors_data = {field: value for field, value in errors_on_interface}
                self._log_event(
                    category=EventCategory.IO,
                    description=f"Network error detected on {interface_name}: [{', '.join(error_names)}]",
                    data={
                        "interface": interface_name,
                        "errors": errors_data,
                    },
                    priority=EventPriority.ERROR,
                    console_log=True,
                )

        if error_state:
            self.result.message = "Network errors detected in statistics"
            self.result.status = ExecutionStatus.ERROR
        else:
            self.result.message = "No network errors detected in statistics"
            self.result.status = ExecutionStatus.OK
        return self.result
