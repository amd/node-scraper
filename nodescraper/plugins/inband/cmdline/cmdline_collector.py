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

from .cmdlinedata import CmdlineDataModel


class CmdlineCollector(InBandDataCollector[CmdlineDataModel, None]):
    """Read linux cmdline data"""

    SUPPORTED_OS_FAMILY = {OSFamily.LINUX}

    DATA_MODEL = CmdlineDataModel

    def collect_data(
        self,
        args=None,
    ) -> tuple[TaskResult, Optional[CmdlineDataModel]]:
        """
        Collects the cmdline data from the system.

        Returns:
            tuple[TaskResult, Optional[CmdlineDataModel]]: tuple containing the task result and the cmdline data model if successful, otherwise None.
        """
        res = self._run_sut_cmd("cat /proc/cmdline")
        cmdline_data = None
        if res.exit_code == 0:
            cmdline_data = CmdlineDataModel(cmdline=res.stdout)
            self._log_event(
                category="CMDLINE_READ",
                description="cmdline read",
                data=cmdline_data.model_dump(),
                priority=EventPriority.INFO,
            )
            self.result.message = f"cmdline: {res.stdout}"
            self.result.status = ExecutionStatus.OK
        else:
            self._log_event(
                category=EventCategory.OS,
                description="Error checking cmdline",
                data={"command": res.command, "exit_code": res.exit_code},
                priority=EventPriority.ERROR,
                console_log=True,
            )
            self.result.message = "cmdline not found"
            self.result.status = ExecutionStatus.ERROR

        return self.result, cmdline_data
