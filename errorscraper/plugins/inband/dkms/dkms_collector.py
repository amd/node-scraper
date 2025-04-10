from errorscraper.enums import EventPriority, ExecutionStatus, OSFamily
from errorscraper.interfaces import InBandDataCollector
from errorscraper.models import TaskResult

from .dkmsdata import DkmsDataModel


class DkmsCollector(InBandDataCollector[DkmsDataModel, None]):
    """Collect DKMS status and version data"""

    SUPPORTED_OS_FAMILY = {OSFamily.LINUX}

    DATA_MODEL = DkmsDataModel

    def collect_data(
        self,
        args=None,
    ) -> tuple[TaskResult, DkmsDataModel | None]:
        """Read dkms status and version"""

        dkms_data = DkmsDataModel()
        dkms_status = self._run_sut_cmd("dkms status")
        dkms_version = self._run_sut_cmd("dkms --version")

        if dkms_status.exit_code == 0:
            dkms_data.status = dkms_status.stdout

        if dkms_version.exit_code == 0:
            dkms_data.version = dkms_version.stdout

        dkms = bool(dkms_data.model_fields_set)
        if dkms:
            self._log_event(
                category="DKMS_READ",
                description="DKMS data read",
                data=dkms_data.model_dump(),
                priority=EventPriority.INFO,
            )
        self.result.message = f"DKMS: {dkms_data.model_dump()}" if dkms else "DKMS info not found"
        self.result.status = ExecutionStatus.OK if dkms else ExecutionStatus.ERROR
        return self.result, dkms_data if dkms else None
