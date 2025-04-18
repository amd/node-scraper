import re

from errorscraper.base import InBandDataCollector
from errorscraper.enums import EventCategory, EventPriority, ExecutionStatus, OSFamily
from errorscraper.models import TaskResult

from .lastdata import LastData, LastDataModel


class LastCollector(InBandDataCollector):
    """
    Collect data from last command with options:

    -F: display full login/logout date and times
    -d: display time in more readable format
    -i: display IP address in dot notation
    -w: display full user and domain names

    """

    DATA_MODEL = LastDataModel

    SUPPORTED_OS_FAMILY: set[OSFamily] = {OSFamily.LINUX}

    LAST_CMD = "last -Fiwd"

    def collect_data(self, args=None) -> tuple[TaskResult, LastDataModel | None]:
        """Read last data"""
        last_data: list[LastData] = []

        last_pattern = re.compile(
            r"(?P<user>\w+)\s+"
            r"(?P<terminal>\S+(\s+\S+)*)\s+"
            r"(?P<ip_address>(?:\d+\.){3}\d+)\s+"
            r"(?P<login_time>\w+\s+\w+\s+\d+\s+\d{2}:\d{2}:\d{2}\s+\d{4})\s+"
            r"(-\s+(?P<logout_time>\w+\s+\w+\s+\d+\s+\d{2}:\d{2}:\d{2}\s+\d{4})\s*)?"
            r"(\((?P<duration>.*)\)\s*)?"
        )

        res = self._run_sut_cmd(self.LAST_CMD)

        if res.exit_code == 0:
            lines = res.stdout.splitlines()
            for line in lines:
                match = last_pattern.match(line)
                if match:
                    user = match.group("user")
                    terminal = match.group("terminal")
                    ip_address = match.group("ip_address")
                    login_time = match.group("login_time")
                    logout_time = match.group("logout_time")
                    duration = match.group("duration")

                    last_data.append(
                        LastData(
                            user=user,
                            terminal=terminal,
                            ip_address=ip_address,
                            login_time=login_time,
                            logout_time=logout_time,
                            duration=duration,
                        )
                    )
        else:
            self._log_event(
                category=EventCategory.OS,
                description="Error running last command",
                data={"command": res.command, "exit_code": res.exit_code},
                priority=EventPriority.ERROR,
                console_log=True,
            )
            self.result.message = "Failed to run last command"
            self.result.status = ExecutionStatus.EXECUTION_FAILURE
            return self.result, None

        last_data_model = LastDataModel(last_data=last_data)

        # only send first 5 entries of last command to event log
        last_data_dump = LastDataModel(last_data=last_data[:5])

        self._log_event(
            category=EventCategory.OS,
            description="Last data collected",
            data=last_data_dump.model_dump(),
            priority=EventPriority.INFO,
        )
        self.result.message = "Last data collected successfully"
        self.result.status = ExecutionStatus.OK
        return self.result, last_data_model
