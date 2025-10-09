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
from nodescraper.connection.inband.inband import CommandArtifact
from nodescraper.enums import EventCategory, EventPriority, OSFamily
from nodescraper.models import TaskResult, TaskStatus
from nodescraper.plugins.inband.devenumdata import DeviceEnumerationDataModel


class DeviceEnumerationCollector(InBandDataCollector[DeviceEnumerationDataModel]):
    """Collect CPU and GPU count"""

    DATA_MODEL = DeviceEnumerationDataModel

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

    def collect_data(self, args=None) -> tuple[TaskResult, DeviceEnumerationDataModel | None]:
        """
        Read CPU and GPU count
        On Linux, use lscpu and lspci
        On Windows, use WMI and hyper-v cmdlets
        """
        device_enum = None
        if self.system_info.os_family == OSFamily.LINUX:
            baremetal_device_id = self.system_info.devid_ep
            sriov_device_id = self.system_info.devid_ep_vf

            cpu_count_res = self._run_system_command("lscpu | grep Socket | awk '{ print $2 }'")
            gpu_count_res = self._run_system_command(f"lspci -d :{baremetal_device_id} | wc -l")
            vf_count_res = self._run_system_command(f"lspci -d :{sriov_device_id} | wc -l")
        else:
            cpu_count_res = self._run_system_command(
                'powershell -Command "(Get-WmiObject -Class Win32_Processor | Measure-Object).Count"'
            )
            gpu_count_res = self._run_system_command(
                'powershell -Command "(wmic path win32_VideoController get name | findstr AMD | Measure-Object).Count"'
            )
            vf_count_res = self._run_system_command(
                'powershell -Command "(Get-VMHostPartitionableGpu | Measure-Object).Count"'
            )
        cpu_count, gpu_count, vf_count = [None, None, None]

        if cpu_count_res.exit_code == 0:
            cpu_count = int(cpu_count_res.stdout)
        else:
            self._warning(description="Cannot determine CPU count", command=cpu_count_res)

        if gpu_count_res.exit_code == 0:
            gpu_count = int(gpu_count_res.stdout)
        else:
            self._warning(description="Cannot determine GPU count", command=gpu_count_res)

        if vf_count_res.exit_code == 0:
            vf_count = int(vf_count_res.stdout)
        else:
            self._warning(
                description="Cannot determine VF count",
                command=vf_count_res,
                category=EventCategory.SW_DRIVER,
            )

        if cpu_count or gpu_count or vf_count:
            device_enum = DeviceEnumerationDataModel(
                cpu_count=cpu_count, gpu_count=gpu_count, vf_count=vf_count
            )
            self._log_event(
                category=EventCategory.PLATFORM,
                description=f"Counted {device_enum.cpu_count} CPUs, {device_enum.gpu_count} GPUs, {device_enum.vf_count} VFs",
                data=device_enum.model_dump(exclude_none=True),
                priority=EventPriority.INFO,
            )
            self.result.message = f"Device Enumeration: {device_enum.model_dump(exclude_none=True)}"
            self.result.status = TaskStatus.OK
        else:
            self.result.message = "Device Enumeration info not found"
            self.result.status = TaskStatus.EXECUTION_FAILURE
            self._log_event(
                category=EventCategory.SW_DRIVER,
                description=self.result.message,
                priority=EventPriority.CRITICAL,
            )

        return self.result, device_enum
