from typing import Optional

from errorscraper.enums import EventCategory, EventPriority, ExecutionStatus
from errorscraper.interfaces import DataAnalyzer
from errorscraper.models import TaskResult
from errorscraper.utils import bytes_to_human_readable, convert_to_bytes

from .analyzer_args import StorageAnalyzerArgs
from .storagedata import StorageDataModel


class StorageAnalyzer(DataAnalyzer[StorageDataModel, StorageAnalyzerArgs]):
    """Check storage usage"""

    DATA_MODEL = StorageDataModel

    def analyze_data(
        self, data: StorageDataModel, args: Optional[StorageAnalyzerArgs] = None
    ) -> TaskResult:
        """
        Check that at least one of the storage devices on the system (e.g. /dev/sda, dev/nvme0n1 or C:) has enough free space.
        If none of the devices have enough free space, log an event with the storage info of the largest device by total size.
        Args:
            min_required_free_space (str): Minimum required free space on at least one of the storage devices
             for the system to be considered healthy. Can be passed with any storage unit (e.g. 2TB, 200Gi)
        """
        if args is None:
            args = StorageAnalyzerArgs()

        min_free = convert_to_bytes(args.min_required_free_space)
        if not data.storage_data:
            self.result.message = "No storage data available"
            self.result.status = ExecutionStatus.NOT_RAN
            return self.result

        for device_name, device_data in data.storage_data.items():
            free = convert_to_bytes(str(device_data.free))
            if free > min_free:
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
                description=f"{self.result.message} {largest_percent}% used on {largest_device}",
                data=event_data,
                priority=EventPriority.CRITICAL,
                console_log=True,
            )
        return self.result
