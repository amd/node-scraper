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
import re
from typing import Optional

from nodescraper.enums import EventCategory, EventPriority, ExecutionStatus
from nodescraper.interfaces import DataAnalyzer
from nodescraper.models import TaskResult

from .analyzer_args import DkmsAnalyzerArgs
from .dkmsdata import DkmsDataModel


class DkmsAnalyzer(DataAnalyzer[DkmsDataModel, DkmsAnalyzerArgs]):
    """Check dkms matches expected status and version"""

    DATA_MODEL = DkmsDataModel

    def analyze_data(
        self, data: DkmsDataModel, args: Optional[DkmsAnalyzerArgs] = None
    ) -> TaskResult:
        """
        Analyze the provided DKMS data against the expected status and version.

        Args:
            data (DkmsDataModel): Dkms data to analyze.
            args (Optional[DkmsAnalyzerArgs], optional): Dkms analysis arguments. Defaults to None.

        Returns:
            TaskResult: The result of the analysis containing status and message.
        """
        # Check if the required data is provided
        if not args:
            self.result.message = "DKMS analysis args not provided"
            self.result.status = ExecutionStatus.NOT_RAN
            return self.result

        # Convert the status and version to lists if they are not already
        check_map = {
            "status": args.dkms_status,
            "version": args.dkms_version,
        }

        error_state = False

        actual_values = []
        expected_values = []
        for check, accepted_values in check_map.items():
            actual_value = getattr(data, check)
            for accepted_value in accepted_values:
                if args.regex_match:
                    try:
                        regex_data = re.compile(accepted_value)
                    except re.error:
                        self._log_event(
                            category=EventCategory.RUNTIME,
                            description=f"DKMS {check} regex is invalid",
                            data={"regex": accepted_value},
                            priority=EventPriority.ERROR,
                        )
                    if regex_data.match(actual_value):
                        break
                elif actual_value == accepted_value:
                    break
            else:
                expected_values.append(accepted_values)
                actual_values.append(actual_value)
                self._log_event(
                    category=EventCategory.SW_DRIVER,
                    description=f"DKMS {check} has an unexpected value",
                    data={"expected": accepted_values, "actual": actual_value},
                    priority=EventPriority.CRITICAL,
                    console_log=True,
                )
                error_state = True

        if error_state:
            self.result.status = ExecutionStatus.ERROR
            self.result.message = (
                f"DKMS data mismatch. \nActual: {actual_values}.\nExpected: {expected_values}"
            )

        return self.result
