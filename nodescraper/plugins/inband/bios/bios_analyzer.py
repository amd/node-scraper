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

from .analyzer_args import BiosAnalyzerArgs
from .biosdata import BiosDataModel


class BiosAnalyzer(DataAnalyzer[BiosDataModel, BiosAnalyzerArgs]):
    """Check bios matches expected bios details"""

    DATA_MODEL = BiosDataModel

    def analyze_data(
        self, data: BiosDataModel, args: Optional[BiosAnalyzerArgs] = None
    ) -> TaskResult:
        """Analyze the BIOS data against expected BIOS versions.

        Args:
            data (BiosDataModel): The BIOS data to analyze.
            args (Optional[BiosAnalyzerArgs], optional): Expected BIOS data. Defaults to None.

        Returns:
            TaskResult: The result of the analysis, indicating whether the BIOS data matches
            the expected versions or not.
        """

        if not args or not (
            args.exp_bios_version or args.exp_server_vendor or args.exp_server_model
        ):
            self.result.message = "Expected bios not provided"
            self.result.status = ExecutionStatus.NOT_RAN
            return self.result

        failures: list[str] = []
        if args.exp_bios_version and not self._matches_expected(
            data.bios_version, args.exp_bios_version, args.regex_match
        ):
            failures.append("Bios data mismatch!")
            self._log_event(
                category=EventCategory.BIOS,
                description=(
                    f"Bios data mismatch! Expected {args.exp_bios_version}, "
                    f"actual: {data.bios_version}"
                ),
                data={
                    "actual_bios_version": data.bios_version,
                    "expected_bios_version": args.exp_bios_version,
                },
                priority=EventPriority.ERROR,
                console_log=True,
            )

        if args.exp_server_vendor and not self._matches_expected(
            data.server_vendor, args.exp_server_vendor, args.regex_match
        ):
            failures.append("Server vendor mismatch!")
            self._log_event(
                category=EventCategory.PLATFORM,
                description=(
                    f"Server vendor mismatch! Expected {args.exp_server_vendor}, "
                    f"actual: {data.server_vendor}"
                ),
                data={
                    "actual_server_vendor": data.server_vendor,
                    "expected_server_vendor": args.exp_server_vendor,
                },
                priority=EventPriority.ERROR,
                console_log=True,
            )

        if args.exp_server_model and not self._matches_expected(
            data.server_model, args.exp_server_model, args.regex_match
        ):
            failures.append("Server model mismatch!")
            self._log_event(
                category=EventCategory.PLATFORM,
                description=(
                    f"Server model mismatch! Expected {args.exp_server_model}, "
                    f"actual: {data.server_model}"
                ),
                data={
                    "actual_server_model": data.server_model,
                    "expected_server_model": args.exp_server_model,
                },
                priority=EventPriority.ERROR,
                console_log=True,
            )

        if not failures:
            self.result.message = "Bios data matches expected"
            self.result.status = ExecutionStatus.OK
        else:
            self.result.message = " ".join(failures)
            self.result.status = ExecutionStatus.ERROR
        return self.result

    def _matches_expected(
        self, actual: Optional[str], expected: list[str], regex_match: bool
    ) -> bool:
        """Return True when actual matches one expected value.

        Invalid regex patterns are logged and skipped, matching the previous BIOS
        version behavior of recording that error and then failing the check.
        """
        if actual is None:
            return False
        for item in expected:
            self.logger.info(item)
            if regex_match:
                try:
                    pattern = re.compile(item)
                except re.error:
                    self._log_event(
                        category=EventCategory.BIOS,
                        description=f"Invalid regex pattern: {item}",
                        priority=EventPriority.ERROR,
                    )
                    continue
                if pattern.match(actual):
                    return True
            elif actual == item:
                return True
        return False
