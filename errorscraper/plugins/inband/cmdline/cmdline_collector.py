from errorscraper.base import InBandDataCollector
from errorscraper.enums import EventCategory, EventPriority, ExecutionStatus, OSFamily
from errorscraper.models import TaskResult

from .cmdlinedata import CmdlineDataModel


class CmdlineCollector(InBandDataCollector[CmdlineDataModel, None]):
    """Read linux cmdline data"""

    SUPPORTED_OS_FAMILY = {OSFamily.LINUX}

    DATA_MODEL = CmdlineDataModel

    def collect_data(
        self,
        args=None,
    ) -> tuple[TaskResult, CmdlineDataModel | None]:
        res = self._run_sut_cmd("cat /proc/cmdline")
        cmdline_data = None
        if res.exit_code == 0:
            cmdline_data = CmdlineDataModel(cmdline=res.stdout)
            self._log_event(
                category="CMDLINE_READ",
                description="cmdline read",
                data=cmdline_data.model_dump(),
                priority=EventPriority.INFO,
            )
            self.result.message = f"cmdline: {res.stdout}"
            self.result.status = ExecutionStatus.OK
        else:
            self._log_event(
                category=EventCategory.OS,
                description="Error checking cmdline",
                data={"command": res.command, "exit_code": res.exit_code},
                priority=EventPriority.ERROR,
                console_log=True,
            )
            self.result.message = "cmdline not found"
            self.result.status = ExecutionStatus.ERROR

        return self.result, cmdline_data
