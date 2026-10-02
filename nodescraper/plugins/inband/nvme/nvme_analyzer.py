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

from .analyzer_args import NvmeAnalyzerArgs
from .nvmedata import NvmeDataModel


class NvmeAnalyzer(DataAnalyzer[NvmeDataModel, NvmeAnalyzerArgs]):
    """Check NVMe SMART health data."""

    DATA_MODEL = NvmeDataModel

    @staticmethod
    def _parse_media_errors(smart_log: Optional[str]) -> Optional[int]:
        if not smart_log:
            return None
        match = re.search(r"(?im)^\s*media_errors\s*:\s*(\d+)\s*$", smart_log)
        return int(match.group(1)) if match else None

    def analyze_data(
        self, data: NvmeDataModel, args: Optional[NvmeAnalyzerArgs] = None
    ) -> TaskResult:
        """Check each NVMe device's SMART media error count."""
        if args is None or args.maximum_smart_error_count is None:
            self.result.status = ExecutionStatus.NOT_RAN
            self.result.message = "Maximum NVMe SMART error count not provided"
            return self.result

        if not data.devices:
            self.result.status = ExecutionStatus.NOT_RAN
            self.result.message = "No NVMe data available"
            return self.result

        failures = []
        for device, device_data in data.devices.items():
            media_errors = self._parse_media_errors(device_data.smart_log)
            if media_errors is None:
                self._log_event(
                    category=EventCategory.STORAGE,
                    description=f"NVMe SMART media error count unavailable for {device}",
                    priority=EventPriority.WARNING,
                    data={"device": device},
                    console_log=True,
                )
                continue

            if media_errors > args.maximum_smart_error_count:
                failures.append((device, media_errors))

        if failures:
            for device, media_errors in failures:
                self._log_event(
                    category=EventCategory.STORAGE,
                    description=(
                        f"NVMe SMART media errors exceeded threshold for {device}: "
                        f"{media_errors} > {args.maximum_smart_error_count}"
                    ),
                    priority=EventPriority.ERROR,
                    data={
                        "device": device,
                        "media_errors": media_errors,
                        "maximum_smart_error_count": args.maximum_smart_error_count,
                    },
                    console_log=True,
                )
            self.result.status = ExecutionStatus.ERROR
            self.result.message = "NVMe SMART media error threshold exceeded"
        else:
            self.result.status = ExecutionStatus.OK
            self.result.message = "NVMe SMART media error counts are within limits"

        return self.result
