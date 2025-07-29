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
import os
import re

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
        """Collect detailed NVMe information from all NVMe devices.

        Returns:
            tuple[TaskResult, NvmeDataModel | None]: Task result and data model with NVMe command outputs.
        """
        if self.system_info.os_family == OSFamily.WINDOWS:
            self._log_event(
                category=EventCategory.SW_DRIVER,
                description="NVMe collection not supported on Windows",
                priority=EventPriority.WARNING,
            )
            self.result.message = "NVMe data collection skipped on Windows"
            self.result.status = ExecutionStatus.NOT_RAN
            return self.result, None

        nvme_devices = self._get_nvme_devices()
        if not nvme_devices:
            self._log_event(
                category=EventCategory.SW_DRIVER,
                description="No NVMe devices found",
                priority=EventPriority.ERROR,
            )
            self.result.message = "No NVMe devices found"
            self.result.status = ExecutionStatus.ERROR
            return self.result, None

        all_device_data = {}

        for dev in nvme_devices:
            device_data = {}
            commands = {
                "smart_log": f"nvme smart-log {dev}",
                "error_log": f"nvme error-log {dev} --log-entries=256",
                "id_ctrl": f"nvme id-ctrl {dev}",
                "id_ns": f"nvme id-ns {dev}n1",
                "fw_log": f"nvme fw-log {dev}",
                "self_test_log": f"nvme self-test-log {dev}",
                "get_log": f"nvme get-log {dev} --log-id=6 --log-len=512",
            }

            for key, cmd in commands.items():
                res = self._run_sut_cmd(cmd, sudo=True)
                if res.exit_code == 0:
                    device_data[key] = res.stdout
                else:
                    self._log_event(
                        category=EventCategory.SW_DRIVER,
                        description=f"Failed to execute NVMe command: '{cmd}'",
                        data={"command": cmd, "exit_code": res.exit_code},
                        priority=EventPriority.WARNING,
                        console_log=True,
                    )

            if device_data:
                all_device_data[os.path.basename(dev)] = device_data

        if all_device_data:
            try:
                nvme_data = NvmeDataModel(devices=all_device_data)
            except ValidationError as e:
                self._log_event(
                    category=EventCategory.SW_DRIVER,
                    description="Validation error while building NvmeDataModel",
                    data={"error": str(e)},
                    priority=EventPriority.ERROR,
                )
                self.result.message = "NVMe data invalid format"
                self.result.status = ExecutionStatus.ERROR
                return self.result, None

            self._log_event(
                category=EventCategory.SW_DRIVER,
                description="Collected NVMe data",
                data=nvme_data.model_dump(),
                priority=EventPriority.INFO,
            )
            self.result.message = "NVMe data successfully collected"
            self.result.status = ExecutionStatus.OK
            return self.result, nvme_data
        else:
            self._log_event(
                category=EventCategory.SW_DRIVER,
                description="Failed to collect any NVMe data",
                priority=EventPriority.ERROR,
            )
            self.result.message = "No NVMe data collected"
            self.result.status = ExecutionStatus.ERROR
            return self.result, None

    def _get_nvme_devices(self) -> list[str]:
        nvme_devs = []
        for entry in os.listdir("/dev"):
            full_path = os.path.join("/dev", entry)

            if re.fullmatch(r"nvme\d+$", entry) and os.path.exists(full_path):
                nvme_devs.append(full_path)
        return nvme_devs
