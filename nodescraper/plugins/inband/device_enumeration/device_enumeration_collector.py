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
from nodescraper.connection.inband.inband import CommandArtifact
from nodescraper.enums import EventCategory, EventPriority, ExecutionStatus, OSFamily
from nodescraper.models import TaskResult

from .deviceenumdata import DeviceEnumerationDataModel


class DeviceEnumerationCollector(InBandDataCollector[DeviceEnumerationDataModel, None]):
    """Collect CPU and GPU count"""

    DATA_MODEL = DeviceEnumerationDataModel

    CMD_CPU_COUNT_LINUX = "lscpu | grep Socket | awk '{ print $2 }'"
    CMD_GPU_COUNT_LINUX = "lspci -d {vendorid_ep}: | grep -i 'VGA\\|Display\\|3D' | wc -l"
    CMD_VF_COUNT_LINUX = "lspci -d {vendorid_ep}: | grep -i 'Virtual Function' | wc -l"

    CMD_CPU_COUNT_WINDOWS = (
        'powershell -Command "(Get-WmiObject -Class Win32_Processor | Measure-Object).Count"'
    )
    CMD_GPU_COUNT_WINDOWS = 'powershell -Command "(wmic path win32_VideoController get name | findstr AMD | Measure-Object).Count"'
    CMD_VF_COUNT_WINDOWS = (
        'powershell -Command "(Get-VMHostPartitionableGpu | Measure-Object).Count"'
    )

    def _warning(
        self,
        description: str,
        command: CommandArtifact,
        category: EventCategory = EventCategory.PLATFORM,
    ):
        self._log_event(
            category=category,
            description=description,
            data={
                "command": command.command,
                "stdout": command.stdout,
                "stderr": command.stderr,
                "exit_code": command.exit_code,
            },
            priority=EventPriority.WARNING,
        )

    def collect_data(self, args=None) -> tuple[TaskResult, Optional[DeviceEnumerationDataModel]]:
        """
        Read CPU and GPU count
        On Linux, use lscpu and lspci
        On Windows, use WMI and hyper-v cmdlets
        """
        if self.system_info.os_family == OSFamily.LINUX:
            # Count CPU sockets
            cpu_count_res = self._run_sut_cmd(self.CMD_CPU_COUNT_LINUX)

            # Count all AMD GPUs
            vendor_id = format(self.system_info.vendorid_ep, "x")
            gpu_count_res = self._run_sut_cmd(
                self.CMD_GPU_COUNT_LINUX.format(vendorid_ep=vendor_id)
            )

            # Count AMD Virtual Functions
            vf_count_res = self._run_sut_cmd(self.CMD_VF_COUNT_LINUX.format(vendorid_ep=vendor_id))
        else:
            cpu_count_res = self._run_sut_cmd(self.CMD_CPU_COUNT_WINDOWS)
            gpu_count_res = self._run_sut_cmd(self.CMD_GPU_COUNT_WINDOWS)
            vf_count_res = self._run_sut_cmd(self.CMD_VF_COUNT_WINDOWS)

        device_enum = DeviceEnumerationDataModel()

        if cpu_count_res.exit_code == 0:
            device_enum.cpu_count = int(cpu_count_res.stdout)
        else:
            self._warning(description="Cannot determine CPU count", command=cpu_count_res)

        if gpu_count_res.exit_code == 0:
            device_enum.gpu_count = int(gpu_count_res.stdout)
        else:
            self._warning(description="Cannot determine GPU count", command=gpu_count_res)

        if vf_count_res.exit_code == 0:
            device_enum.vf_count = int(vf_count_res.stdout)
        else:
            self._warning(
                description="Cannot determine VF count",
                command=vf_count_res,
                category=EventCategory.SW_DRIVER,
            )

        if device_enum.cpu_count or device_enum.gpu_count or device_enum.vf_count:
            self._log_event(
                category=EventCategory.PLATFORM,
                description=f"Counted {device_enum.cpu_count} CPUs, {device_enum.gpu_count} GPUs, {device_enum.vf_count} VFs",
                data=device_enum.model_dump(exclude_none=True),
                priority=EventPriority.INFO,
            )
            self.result.message = f"Device Enumeration: {device_enum.model_dump(exclude_none=True)}"
            self.result.status = ExecutionStatus.OK
            return self.result, device_enum
        else:
            self.result.message = "Device Enumeration info not found"
            self.result.status = ExecutionStatus.EXECUTION_FAILURE
            self._log_event(
                category=EventCategory.SW_DRIVER,
                description=self.result.message,
                priority=EventPriority.CRITICAL,
            )
            return self.result, None
