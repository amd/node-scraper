from errorscraper.base import InBandDataCollector
from errorscraper.enums import EventCategory, EventPriority, ExecutionStatus, OSFamily
from errorscraper.models import TaskResult

from .kerneldata import KernelDataModel


class KernelCollector(InBandDataCollector[KernelDataModel, None]):
    """Read kernel version"""

    DATA_MODEL = KernelDataModel

    def collect_data(
        self,
        args=None,
    ) -> tuple[TaskResult, KernelDataModel | None]:
        """read kernel data"""
        kernel = None
        if self.system_info.os_family == OSFamily.WINDOWS:
            res = self._run_sut_cmd("wmic os get Version /Value")
            if res.exit_code == 0:
                kernel = [line for line in res.stdout.splitlines() if "Version=" in line][0].split(
                    "="
                )[1]
        else:
            res = self._run_sut_cmd("sh -c 'uname -r'", sudo=True)
            if res.exit_code == 0:
                kernel = res.stdout

        if res.exit_code != 0:
            self._log_event(
                category=EventCategory.OS,
                description="Error checking kernel version",
                data={"command": res.command, "exit_code": res.exit_code},
                priority=EventPriority.ERROR,
                console_log=True,
            )

        if kernel:
            kernel_data = KernelDataModel(kernel_version=kernel)
            self._log_event(
                category="KERNEL_READ",
                description="Kernel version read",
                data=kernel_data.model_dump(),
                priority=EventPriority.INFO,
            )
        else:
            kernel_data = None

        self.result.message = f"Kernel: {kernel}" if kernel else "Kernel not found"
        self.result.status = ExecutionStatus.OK if kernel else ExecutionStatus.ERROR
        return self.result, kernel_data
