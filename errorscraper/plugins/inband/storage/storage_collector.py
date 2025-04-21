import re

from errorscraper.base import InBandDataCollector
from errorscraper.enums import EventCategory, EventPriority, ExecutionStatus, OSFamily
from errorscraper.models import TaskResult

from .storagedata import DeviceStorageData, StorageDataModel


class StorageCollector(InBandDataCollector[StorageDataModel, None]):
    """Collect disk usage details"""

    DATA_MODEL = StorageDataModel

    def collect_data(self, args=None) -> tuple[TaskResult, StorageDataModel | None]:
        """read storage usage data"""
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
