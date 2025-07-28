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

from .storagedata import DeviceStorageData, StorageDataModel


class StorageCollector(InBandDataCollector[StorageDataModel, None]):
    """Collect disk usage details"""

    DATA_MODEL = StorageDataModel

    def collect_data(self, args: None = None) -> tuple[TaskResult, StorageDataModel | None]:
        """read storage usage data"""
        if args.skip_sudo:
            self.result.message = "Skipping sudo plugin"
            self.result.status = ExecutionStatus.NOT_RAN
            return self.result, None
        storage_data = {}
        if self.system_info.os_family == OSFamily.WINDOWS:
            res = self._run_sut_cmd(
                'wmic LogicalDisk Where DriveType="3" Get DeviceId,Size,FreeSpace'
            )
            if res.exit_code == 0:
                for line in res.stdout.splitlines()[1:]:
                    if line:
                        device_id, free_space, size = line.split()
                        storage_data[device_id] = DeviceStorageData(
                            total=int(size),
                            free=int(free_space),
                            used=int(size) - int(free_space),
                            percent=round((int(size) - int(free_space)) / int(size) * 100, 2),
                        )
        else:
            res = self._run_sut_cmd("""sh -c 'df -lH -B1 | grep -v 'boot''""", sudo=True)
            if res.exit_code == 0:
                for line in res.stdout.splitlines()[1:]:
                    if line:
                        device_id, size, used, available, percent = line.strip().split()[:5]
                        if device_id not in ["tmpfs", "overlay"]:
                            storage_data[device_id] = DeviceStorageData(
                                total=int(size),
                                free=int(available),
                                used=int(used),
                                percent=float(re.sub(r"%", "", percent)),
                            )

        if res.exit_code != 0:
            self._log_event(
                category=EventCategory.OS,
                description="Error checking available storage",
                data={
                    "command": res.command,
                    "exit_code": res.exit_code,
                    "stderr": res.stderr,
                },
                priority=EventPriority.ERROR,
                console_log=True,
            )

        if storage_data:
            storage_data = dict(sorted(storage_data.items(), key=lambda x: x[1].total))
            storage_model = StorageDataModel(storage_data=storage_data)
            self._log_event(
                category="STORAGE_READ",
                description="Available storage read",
                data=storage_model.model_dump(),
                priority=EventPriority.INFO,
            )
            self.result.message = f"{len(storage_model.storage_data)} storage devices collected"
            self.result.status = ExecutionStatus.OK
        else:
            storage_model = None
            self.result.message = "Storage info not found"
            self.result.status = ExecutionStatus.ERROR
        return self.result, storage_model
