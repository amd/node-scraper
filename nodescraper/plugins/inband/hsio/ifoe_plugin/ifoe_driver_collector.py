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

from nodescraper.base import InBandDataCollector
from nodescraper.enums import EventCategory, EventPriority, ExecutionStatus, OSFamily
from nodescraper.models import TaskResult

from .ifoe_data import IfoeDataModel


class IfoeDriverCollector(InBandDataCollector[IfoeDataModel, None]):
    """Collect IFoE driver details from modinfo."""

    DATA_MODEL = IfoeDataModel

    SUPPORTED_OS_FAMILY: set[OSFamily] = {OSFamily.LINUX}

    CMD_MODINFO_VERSION = "modinfo ifoe | grep -i version"

    def collect_data(self, args=None) -> tuple[TaskResult, Optional[IfoeDataModel]]:
        """Read IFoE driver version from modinfo."""
        ifoe_data: Optional[IfoeDataModel] = None
        res = self._run_sut_cmd(self.CMD_MODINFO_VERSION)

        if res.exit_code == 0 and res.stdout:
            for line in res.stdout.splitlines():
                if line.startswith("version:"):
                    driver_version = line.split("version:", 1)[1].strip()
                    ifoe_data = IfoeDataModel(driver_version=driver_version)
                    break

            if ifoe_data is None:
                self._log_event(
                    category=EventCategory.SW_DRIVER,
                    description="IFoE driver version field not found.",
                    data={"command": res.command},
                    priority=EventPriority.WARNING,
                )
                self.result.message = "IFoE Driver version not found."
                self.result.status = ExecutionStatus.ERROR
                return self.result, ifoe_data

            self._log_event(
                category=EventCategory.SW_DRIVER,
                description="IFoE Driver version read.",
                data=ifoe_data.model_dump(),
                priority=EventPriority.INFO,
            )
            self.result.message = f"IFoE Driver version: {ifoe_data.driver_version}"
            self.result.status = ExecutionStatus.OK
            return self.result, ifoe_data

        self._log_event(
            category=EventCategory.SW_DRIVER,
            description="Error checking IFoE Driver version.",
            data={"command": res.command, "exit_code": res.exit_code},
            priority=EventPriority.ERROR,
        )
        self.result.message = "Error checking IFoE Driver version."
        self.result.status = ExecutionStatus.ERROR
        return self.result, ifoe_data
