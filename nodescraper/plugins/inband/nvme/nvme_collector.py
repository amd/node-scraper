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
from pydantic import ValidationError

from nodescraper.base import InBandDataCollector
from nodescraper.enums import EventCategory, EventPriority, ExecutionStatus, OSFamily
from nodescraper.models import TaskResult

from .nvmedata import NvmeDataModel


class NvmeCollector(InBandDataCollector[NvmeDataModel, None]):
    """Collect NVMe details from the system."""

    DATA_MODEL = NvmeDataModel

    def collect_data(
        self,
        args=None,
    ) -> tuple[TaskResult, NvmeDataModel | None]:
        """Collect detailed NVMe information from the system.

        Returns:
            tuple[TaskResult, NvmeDataModel | None]: Task result and data model with NVMe command outputs.
        """
        data = {}

        if self.system_info.os_family == OSFamily.WINDOWS:
            self._log_event(
                category=EventCategory.SW_DRIVER,
                description="NVMe collection not supported on Windows",
                priority=EventPriority.WARNING,
            )
            self.result.message = "NVMe data collection skipped on Windows"
            self.result.status = ExecutionStatus.SKIPPED
            return self.result, None

        commands = [
            "nvme smart-log /dev/nvme0",
            "nvme error-log /dev/nvme0 --log-entries=256",
            "nvme id-ctrl /dev/nvme0",
            "nvme id-ns /dev/nvme0n1",
            "nvme fw-log /dev/nvme0",
            "nvme self-test-log /dev/nvme0",
            "nvme get-log /dev/nvme0 --log-id=6 --log-len=512",
        ]

        for cmd in commands:
            res = self._run_sut_cmd(cmd, sudo=True)
            if res.exit_code == 0:
                data[cmd] = res.stdout
            else:
                self._log_event(
                    category=EventCategory.SW_DRIVER,
                    description=f"Failed to execute NVMe command: '{cmd}'",
                    data={"command": cmd, "exit_code": res.exit_code},
                    priority=EventPriority.ERROR,
                    console_log=True,
                )

        nvme_data = None
        if data:
            try:
                nvme_data = NvmeDataModel(nvme_data=data)
            except ValidationError as e:
                self._log_event(
                    category=EventCategory.SW_DRIVER,
                    description="Validation error while building NvmeDataModel",
                    data={"error": str(e)},
                    priority=EventPriority.CRITICAL,
                )
                self.result.message = "NVMe data invalid format"
                self.result.status = ExecutionStatus.ERROR
            # nvme_data = NvmeDataModel(nvme_data=data)
            # self._log_event(
            #    category=EventCategory.SW_DRIVER,
            #    description="Collected NVMe data",
            #    data=nvme_data.model_dump(),
            #    priority=EventPriority.INFO,
            # )
            # self.result.message = "NVMe data successfully collected"
        else:
            nvme_data = None
            self._log_event(
                category=EventCategory.SW_DRIVER,
                description="Failed to collect any NVMe data",
                priority=EventPriority.CRITICAL,
            )
            self.result.message = "No NVMe data collected"
            self.result.status = ExecutionStatus.ERROR

        return self.result, nvme_data
