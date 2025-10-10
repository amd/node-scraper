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

from nodescraper.base import InBandDataCollector
from nodescraper.enums import EventCategory, EventPriority, ExecutionStatus, OSFamily
from nodescraper.models import TaskResult

from .osdata import OsDataModel


class OsCollector(InBandDataCollector[OsDataModel, None]):
    """Collect OS details"""

    DATA_MODEL = OsDataModel

    def collect_version(self) -> str:
        """Collect OS version.

        Returns:
            str: OS version string, empty string if not found.
        """
        if self.system_info.os_family == OSFamily.WINDOWS:
            res = self._run_sut_cmd("wmic os get Version /value")
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
            V_STR = "VERSION_ID"  # noqa: N806
            res = self._run_sut_cmd(f"cat /etc/*release | grep {V_STR}")
            if res.exit_code == 0:
                os_version = res.stdout
                os_version = os_version.removeprefix(f"{V_STR}=")
                os_version = os_version.strip('" ')
            else:
                self._log_event(
                    category=EventCategory.OS,
                    description="OS version not found",
                    priority=EventPriority.ERROR,
                )
                os_version = ""
        return os_version

    def collect_data(self, args=None) -> tuple[TaskResult, Optional[OsDataModel]]:
        """Collect OS name and version.

        Returns:
            tuple[TaskResult, Optional[OsDataModel]]: tuple containing the task result and OS data model or None if not found.
        """
        os_name = None
        if self.system_info.os_family == OSFamily.WINDOWS:
            res = self._run_sut_cmd("wmic os get Caption /Value")
            if res.exit_code == 0:
                os_name = re.search(r"Caption=([\w\s]+)", res.stdout).group(1)
        else:
            PRETTY_STR = "PRETTY_NAME"  # noqa: N806
            res = self._run_sut_cmd(
                f"sh -c '( lsb_release -ds || (cat /etc/*release | grep {PRETTY_STR}) || uname -om ) 2>/dev/null | head -n1'"
            )
            # search for PRETTY_NAME in res
            if res.exit_code == 0:
                if res.stdout.find(PRETTY_STR) != -1:
                    os_name = res.stdout
                    # remove the PRETTY_NAME string
                    os_name = os_name.removeprefix(f"{PRETTY_STR}=")
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
