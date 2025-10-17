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

from nodescraper.base import InBandDataCollector
from nodescraper.enums import EventCategory, EventPriority, ExecutionStatus, OSFamily
from nodescraper.models import TaskResult

from .collector_args import JournalCollectorArgs
from .journaldata import JournalData


class JournalCollector(InBandDataCollector[JournalData, JournalCollectorArgs]):
    """Read journal log via journalctl."""

    SUPPORTED_OS_FAMILY = {OSFamily.LINUX}
    DATA_MODEL = JournalData

    def _read_with_journalctl(self, args: Optional[JournalCollectorArgs] = None):
        """Read journal logs using journalctl

        Returns:
            str|None: system journal read
        """
        boot_arg = ""

        if args is not None:
            try:
                # Accept ints or numeric strings
                boot_arg = f" -b {args.boot}"
            except (TypeError, ValueError):
                pass

        cmd = f"journalctl --no-pager{boot_arg} --system --output=short-iso"
        res = self._run_sut_cmd(cmd, sudo=True, log_artifact=False, strip=False)
        self.result.message = cmd

        if res.exit_code != 0:
            self._log_event(
                category=EventCategory.OS,
                description="Error reading journalctl",
                data={"command": res.command, "exit_code": res.exit_code},
                priority=EventPriority.ERROR,
                console_log=True,
            )
            self.result.message = "Could not read journalctl data"
            self.result.status = ExecutionStatus.ERROR
            return None

        return res.stdout

    def collect_data(
        self,
        args: Optional[JournalCollectorArgs] = None,
    ) -> tuple[TaskResult, JournalData | None]:
        """Collect journal logs

        Args:
            args (_type_, optional): Collection args. Defaults to None.

        Returns:
            tuple[TaskResult, JournalData | None]: Tuple of results and data model or none.
        """
        if args is None:
            args = JournalCollectorArgs()

        journal_log = self._read_with_journalctl(args)
        if journal_log:
            data = JournalData(journal_log=journal_log)
            self.result.message = self.result.message or "Journal data collected"
            return self.result, data
        return self.result, None
