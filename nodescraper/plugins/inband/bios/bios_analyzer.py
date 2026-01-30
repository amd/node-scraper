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

        if not args or not args.exp_bios_version:
            self.result.message = "Expected bios not provided"
            self.result.status = ExecutionStatus.NOT_RAN
            return self.result

        for bios_version in args.exp_bios_version:
            self.logger.info(bios_version)
            if args.regex_match:
                try:
                    bios_regex = re.compile(bios_version)
                except re.error:
                    self._log_event(
                        category=EventCategory.BIOS,
                        description=f"Invalid regex pattern: {bios_version}",
                        priority=EventPriority.ERROR,
                    )
                    continue
                if bios_regex.match(data.bios_version):
                    self.result.message = "Bios data matches expected"
                    self.result.status = ExecutionStatus.OK
                    return self.result
            elif data.bios_version == bios_version:
                self.result.message = "Bios data matches expected"
                self.result.status = ExecutionStatus.OK
                return self.result

        self.result.message = "Bios data mismatch!"
        self.result.status = ExecutionStatus.ERROR
        self._log_event(
            category=EventCategory.BIOS,
            description=f"Bios data mismatch! Expected {args.exp_bios_version}, actual: {data.bios_version}",
            data={
                "actual_bios_version": data.bios_version,
                "expected_bios_version": args.exp_bios_version,
            },
            priority=EventPriority.ERROR,
            console_log=True,
        )
        return self.result
