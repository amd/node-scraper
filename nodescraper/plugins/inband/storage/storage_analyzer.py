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

from nodescraper.enums import EventCategory, EventPriority, ExecutionStatus
from nodescraper.interfaces import DataAnalyzer
from nodescraper.models import TaskResult
from nodescraper.utils import bytes_to_human_readable, convert_to_bytes

from .analyzer_args import StorageAnalyzerArgs
from .storagedata import StorageDataModel


class StorageAnalyzer(DataAnalyzer[StorageDataModel, StorageAnalyzerArgs]):
    """Check storage usage"""

    DATA_MODEL = StorageDataModel

    def analyze_data(
        self, data: StorageDataModel, args: Optional[StorageAnalyzerArgs] = None
    ) -> TaskResult:
        """Analyze the storage data to check if there is enough free space

        Args:
            data (StorageDataModel): storage data to analyze
            args (Optional[StorageAnalyzerArgs], optional): storage analysis arguments. Defaults to None.

        Returns:
            TaskResult: Result of the storage analysis containing the status and message.
        """
        if args is None:
            args = StorageAnalyzerArgs()

        if not data.storage_data:
            self.result.message = "No storage data available"
            self.result.status = ExecutionStatus.NOT_RAN
            return self.result

        for device_name, device_data in data.storage_data.items():
            condition = False
            if args.min_required_free_space_abs:
                min_free_abs = convert_to_bytes(args.min_required_free_space_abs)
                free_abs = convert_to_bytes(str(device_data.free))
                if free_abs and free_abs > min_free_abs:
                    condition = True
            else:
                condition = True

            free_prct = 100 - device_data.percent
            condition = condition and (free_prct < args.min_required_free_space_prct)

            if condition:
                self.result.message = f"'{device_name}' has {bytes_to_human_readable(device_data.free)} available, {device_data.percent}% used"
                self.result.status = ExecutionStatus.OK
                break
            else:
                self.result.message = "Not enough disk storage!"
                self.result.status = ExecutionStatus.ERROR
                # find the device with the largest total storage, and its free space
                largest_device = max(
                    data.storage_data,
                    key=lambda x: convert_to_bytes(str(data.storage_data[x].total)),
                )
                largest_free = data.storage_data[largest_device].free
                largest_percent = data.storage_data[largest_device].percent
                largest_used = data.storage_data[largest_device].used
                event_data = {
                    "largest_device": {
                        "device": largest_device,
                        "total": data.storage_data[largest_device].total,
                        "free": largest_free,
                        "percent": largest_percent,
                    },
                }
                self._log_event(
                    category=EventCategory.STORAGE,
                    description=f"{self.result.message} {bytes_to_human_readable(largest_used)} and {largest_percent}%,  used on {largest_device}",
                    data=event_data,
                    priority=EventPriority.CRITICAL,
                    console_log=True,
                )
        return self.result
