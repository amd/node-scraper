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

from .analyzer_args import ThpAnalyzerArgs
from .thpdata import ThpDataModel


class ThpAnalyzer(DataAnalyzer[ThpDataModel, ThpAnalyzerArgs]):
    """Check THP settings against expected values."""

    DATA_MODEL = ThpDataModel

    def analyze_data(
        self, data: ThpDataModel, args: Optional[ThpAnalyzerArgs] = None
    ) -> TaskResult:
        """Compare THP data to expected settings."""
        mismatches = {}

        if not args:
            args = ThpAnalyzerArgs()

        if args.exp_enabled is not None:
            actual = (data.enabled or "").strip().lower()
            expected = args.exp_enabled.strip().lower()
            if actual != expected:
                mismatches["enabled"] = {"expected": expected, "actual": data.enabled}

        if args.exp_defrag is not None:
            actual = (data.defrag or "").strip().lower()
            expected = args.exp_defrag.strip().lower()
            if actual != expected:
                mismatches["defrag"] = {"expected": expected, "actual": data.defrag}

        if mismatches:
            self.result.status = ExecutionStatus.ERROR
            self.result.message = "THP setting(s) do not match expected values."
            self._log_event(
                category=EventCategory.OS,
                description="THP mismatch detected",
                data=mismatches,
                priority=EventPriority.ERROR,
                console_log=True,
            )
        else:
            self._log_event(
                category=EventCategory.OS,
                description="THP settings match expected (or no expectations set)",
                priority=EventPriority.INFO,
                console_log=True,
            )
            self.result.status = ExecutionStatus.OK
            self.result.message = "THP settings as expected."

        return self.result
