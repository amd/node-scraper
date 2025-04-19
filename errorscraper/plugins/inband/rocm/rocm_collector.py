from errorscraper.base import InBandDataCollector
from errorscraper.enums import EventCategory, EventPriority, ExecutionStatus, OSFamily
from errorscraper.models import TaskResult

from .rocmdata import RocmDataModel


class RocmCollector(InBandDataCollector[RocmDataModel, None]):
    """Collect ROCm version data"""

    SUPPORTED_OS_FAMILY: set[OSFamily] = {OSFamily.LINUX}

    DATA_MODEL = RocmDataModel

    def collect_data(self, args=None) -> tuple[TaskResult, RocmDataModel | None]:
        """read ROCm version data"""
        res = self._run_sut_cmd("cat /opt/rocm/.info/version")
        if res.exit_code == 0:
            rocm_data = RocmDataModel(rocm_version=res.stdout)
            self._log_event(
                category="ROCM_VERSION_READ",
                description="ROCm version data collected",
                data=rocm_data.model_dump(),
                priority=EventPriority.INFO,
            )
            self.result.message = f"ROCm: {rocm_data.model_dump()}"
            self.result.status = ExecutionStatus.OK
        else:
            rocm_data = None
            self._log_event(
                category=EventCategory.OS,
                description="Error checking ROCm version",
                data={
                    "command": res.command,
                    "exit_code": res.exit_code,
                    "stderr": res.stderr,
                },
                priority=EventPriority.ERROR,
                console_log=True,
            )
            self.result.message = "ROCm version not found"
            self.result.status = ExecutionStatus.ERROR

        return self.result, rocm_data
