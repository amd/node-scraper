import re

from errorscraper.base import InBandDataCollector
from errorscraper.enums import EventCategory, EventPriority, ExecutionStatus, OSFamily
from errorscraper.models import TaskResult

from .uptimedata import UptimeDataModel


class UptimeCollector(InBandDataCollector[UptimeDataModel, None]):
    """Collect last boot time and uptime from uptime command"""

    DATA_MODEL = UptimeDataModel

    SUPPORTED_OS_FAMILY: set[OSFamily] = {OSFamily.LINUX}

    UPTIME_CMD = "uptime"

    def collect_data(self, args=None) -> tuple[TaskResult, UptimeDataModel | None]:
        """Read uptime data"""

        uptime_pattern = re.compile(
            r"(?P<current_time>\d{2}:\d{2}:\d{2})\s+" r"up\s+(?P<uptime>.+?),\s+\d+\s+users?"
        )

        res = self._run_sut_cmd(self.UPTIME_CMD)

        if res.exit_code == 0:
            line = res.stdout.strip()
            match = uptime_pattern.match(line)

            if match:
                current_time = match.group("current_time")
                uptime = match.group("uptime")

        else:
            self._log_event(
                category=EventCategory.OS,
                description="Error running uptime command",
                data={"command": res.command, "exit_code": res.exit_code},
                priority=EventPriority.ERROR,
                console_log=True,
            )
            self.result.message = "Failed to run uptime command"
            self.result.status = ExecutionStatus.EXECUTION_FAILURE
            return self.result, None

        uptime_data = UptimeDataModel(current_time=current_time, uptime=uptime)

        self._log_event(
            category=EventCategory.OS,
            description="Uptime data collected",
            data=uptime_data.model_dump(),
            priority=EventPriority.INFO,
        )
        self.result.message = f"Uptime: {uptime}"
        self.result.status = ExecutionStatus.OK
        return self.result, uptime_data
