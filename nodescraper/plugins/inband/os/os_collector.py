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

from nodescraper.base import InBandDataCollector
from nodescraper.enums import EventCategory, EventPriority, ExecutionStatus, OSFamily
from nodescraper.models import TaskResult

from .osdata import OsDataModel


class OsCollector(InBandDataCollector[OsDataModel, None]):
    """Collect OS details"""

    DATA_MODEL = OsDataModel
    CMD_VERSION_WINDOWS = "wmic os get Version /value"
    CMD_VERSION = "cat /etc/*release | grep VERSION_ID"
    CMD_WINDOWS = "wmic os get Caption /Value"
    PRETTY_STR = "PRETTY_NAME"  # noqa: N806
    CMD = f"sh -c '( lsb_release -ds || (cat /etc/*release | grep {PRETTY_STR}) || uname -om ) 2>/dev/null | head -n1'"

    def collect_version(self) -> str:
        """Collect OS version.

        Returns:
            str: OS version string, empty string if not found.
        """
        if self.system_info.os_family == OSFamily.WINDOWS:
            res = self._run_sut_cmd(self.CMD_VERSION_WINDOWS)
            if res.exit_code == 0:
                os_version = re.search(r"Version=([\w\s\.]+)", res.stdout).group(1)
            else:
                self._log_event(
                    category=EventCategory.OS,
                    description="OS version not found",
                    priority=EventPriority.ERROR,
                )
                os_version = ""
        else:
            res = self._run_sut_cmd(self.CMD_VERSION)
            if res.exit_code == 0:
                os_version = res.stdout
                os_version = os_version.removeprefix("VERSION_ID=")
                os_version = os_version.strip('" ')
            else:
                self._log_event(
                    category=EventCategory.OS,
                    description="OS version not found",
                    priority=EventPriority.ERROR,
                )
                os_version = ""
        return os_version

    def collect_data(self, args=None) -> tuple[TaskResult, OsDataModel | None]:
        """Collect OS name and version.

        Returns:
            tuple[TaskResult, OsDataModel | None]: tuple containing the task result and OS data model or None if not found.
        """
        os_name = None
        if self.system_info.os_family == OSFamily.WINDOWS:
            res = self._run_sut_cmd(self.CMD_WINDOWS)
            if res.exit_code == 0:
                os_name = re.search(r"Caption=([\w\s]+)", res.stdout).group(1)
        else:
            res = self._run_sut_cmd(self.CMD)
            # search for PRETTY_NAME in res
            if res.exit_code == 0:
                if res.stdout.find(self.PRETTY_STR) != -1:
                    os_name = res.stdout
                    os_name = os_name.removeprefix(f"{self.PRETTY_STR}=")
                    # remove the ending/starting quotes and spaces
                    os_name = os_name.strip('" ')
                else:
                    os_name = res.stdout
            else:
                self._log_event(
                    category=EventCategory.OS,
                    description="OS name not found",
                    priority=EventPriority.ERROR,
                )

        if os_name:
            os_version = self.collect_version()
            os_data = OsDataModel(
                os_name=os_name,
                os_version=os_version,
            )
            self._log_event(
                category="OS_NAME_READ",
                description="OS name data collected",
                data=os_data.model_dump(),
                priority=EventPriority.INFO,
            )
            self.result.message = f"OS: {os_name}"
            self.result.status = ExecutionStatus.OK
        else:
            os_data = None
            self._log_event(
                category=EventCategory.OS,
                description="OS name not found",
                priority=EventPriority.CRITICAL,
            )
            self.result.message = "OS name not found"
            self.result.status = ExecutionStatus.EXECUTION_FAILURE

        return self.result, os_data
