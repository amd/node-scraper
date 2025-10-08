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

from nodescraper.base import InBandDataCollector
from nodescraper.enums import EventCategory, EventPriority, ExecutionStatus, OSFamily
from nodescraper.models import TaskResult

from .sysctldata import SysctlDataModel


class SysctlCollector(InBandDataCollector[SysctlDataModel, None]):
    """Collect sysctl kernel VM settings."""

    DATA_MODEL = SysctlDataModel
    CMD = "sysctl -n"

    def collect_data(
        self,
        args=None,
    ) -> tuple[TaskResult, SysctlDataModel | None]:
        """Collect sysctl VM tuning values from the system."""
        values = {}

        if self.system_info.os_family == OSFamily.WINDOWS:
            self._log_event(
                category=EventCategory.OS,
                description="Windows is not supported for sysctl collection.",
                priority=EventPriority.WARNING,
                console_log=True,
            )
            return self.result, None

        for field_name in SysctlDataModel.model_fields:
            sysctl_key = field_name.replace("_", ".", 1)
            res = self._run_sut_cmd(f"{self.CMD} {sysctl_key}")

            if res.exit_code == 0:
                try:
                    values[field_name] = int(res.stdout.strip())
                except ValueError:
                    self._log_event(
                        category=EventCategory.OS,
                        description=f"Invalid integer value for {sysctl_key}",
                        data={"stdout": res.stdout},
                        priority=EventPriority.ERROR,
                        console_log=True,
                    )
            else:
                self._log_event(
                    category=EventCategory.OS,
                    description=f"Error checking Linux system setting : {sysctl_key}",
                    data={"system_setting": sysctl_key, "exit_code": res.exit_code},
                    priority=EventPriority.WARNING,
                    console_log=True,
                )

        if values:
            sysctl_data = SysctlDataModel(**values)
            self._log_event(
                category="OS",
                description="Sysctl settings read",
                data=sysctl_data.model_dump(),
                priority=EventPriority.INFO,
            )
            self.result.message = "SYSCTL data collected"
            self.result.status = ExecutionStatus.OK
        else:
            sysctl_data = None
            self._log_event(
                category=EventCategory.OS,
                description="Sysctl settings not read",
                priority=EventPriority.CRITICAL,
            )
            self.result.message = "Sysctl settings not read"
            self.result.status = ExecutionStatus.ERROR

        return self.result, sysctl_data
