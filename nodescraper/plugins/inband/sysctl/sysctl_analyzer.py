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

from .analyzer_args import SysctlAnalyzerArgs
from .sysctldata import SysctlDataModel


class SysctlAnalyzer(DataAnalyzer[SysctlDataModel, SysctlAnalyzerArgs]):
    """Check sysctl matches expected sysctl details"""

    DATA_MODEL = SysctlDataModel

    def analyze_data(
        self, data: SysctlDataModel, args: Optional[SysctlAnalyzerArgs] = None
    ) -> TaskResult:
        """Analyze the Sysctl data against expected Sysctl values."""
        mismatches = {}

        if not args:
            args = SysctlAnalyzerArgs()

        for exp_field_name, expected_value in args.model_dump(exclude_unset=True).items():

            data_field_name = exp_field_name.removeprefix("exp_")
            actual_value = getattr(data, data_field_name, None)

            if actual_value is None:
                mismatches[data_field_name] = {"expected": expected_value, "actual": "missing"}
            elif actual_value != expected_value:
                mismatches[data_field_name] = {"expected": expected_value, "actual": actual_value}

        if mismatches:
            self.result.status = ExecutionStatus.ERROR
            self.result.message = f"{len(mismatches)} sysctl parameter(s) mismatched."
            self._log_event(
                category=EventCategory.OS,
                description="Sysctl mismatch detected",
                data=mismatches,
                priority=EventPriority.ERROR,
                console_log=True,
            )
        else:
            self._log_event(
                category=EventCategory.OS,
                description="All expected sysctl parameters matched",
                priority=EventPriority.INFO,
                console_log=True,
            )
            self.result.status = ExecutionStatus.OK
            self.result.message = "All expected sysctl parameters match."

        return self.result
