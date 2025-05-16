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

from errorscraper.enums import EventCategory, EventPriority, ExecutionStatus
from errorscraper.interfaces import DataAnalyzer
from errorscraper.models import TaskResult

from .analyzer_args import CmdlineAnalyzerArgs
from .cmdlinedata import CmdlineDataModel


class CmdlineAnalyzer(DataAnalyzer[CmdlineDataModel, CmdlineAnalyzerArgs]):
    """Check cmdline matches expected kernel cmdline"""

    DATA_MODEL = CmdlineDataModel

    def _compare_cmdline(self, cmdline: str, required_cmdline: list, banned_cmdline: list) -> bool:
        # Check for missing required arguments
        missing_required = [arg for arg in required_cmdline if arg not in cmdline]
        found_banned = [arg for arg in banned_cmdline if arg in cmdline]

        if len(missing_required) >= 1:
            self._log_event(
                category=EventCategory.OS,
                description=f"Missing {len(missing_required)} required kernel cmdline arguments",
                priority=EventPriority.ERROR,
                data={"missing_required": missing_required},
                console_log=True,
            )

        if len(found_banned) >= 1:
            self._log_event(
                category=EventCategory.OS,
                description=f"Found {len(found_banned)} banned kernel cmdline arguments",
                priority=EventPriority.ERROR,
                data={"found_banned": found_banned},
                console_log=True,
            )

        return not (missing_required or found_banned)

    def analyze_data(
        self, data: CmdlineDataModel, args: Optional[CmdlineAnalyzerArgs] = None
    ) -> TaskResult:

        if not args:
            self.result.message = "Cmdline analysis args not provided"
            self.result.status = ExecutionStatus.NOT_RAN
            return self.result

        # check if any of the cmdline defined in the list match the actual kernel cmdline
        if self._compare_cmdline(data.cmdline, args.required_cmdline, args.banned_cmdline):
            self.result.message = "Kernel cmdline matches expected"
            self.result.status = ExecutionStatus.OK
            return self.result

        self.result.message = "Illegal kernel cmdline"
        self.result.status = ExecutionStatus.ERROR
        self._log_event(
            category=EventCategory.OS,
            description=self.result.message,
            priority=EventPriority.CRITICAL,
            console_log=True,
        )
        return self.result
