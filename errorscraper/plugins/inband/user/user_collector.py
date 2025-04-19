import re

from errorscraper.base import InBandDataCollector
from errorscraper.connection.inband import CommandArtifact
from errorscraper.enums import EventCategory, EventPriority, ExecutionStatus, OSFamily
from errorscraper.models import TaskResult

from .userdata import UserDataModel


class UserCollector(InBandDataCollector[UserDataModel, None]):
    """Collect User details"""

    DATA_MODEL = UserDataModel

    def _handle_command_failure(self, command_artifact: CommandArtifact):
        self._log_event(
            category=EventCategory.OS,
            description=f"Error running command: {command_artifact.command}",
            priority=EventPriority.WARNING,
            data={
                "stderr": command_artifact.stderr,
                "exit_code": command_artifact.exit_code,
            },
        )
        self.result.message = "Failed to run users command"
        self.result.status = ExecutionStatus.EXECUTION_FAILURE

    def collect_data(self, args=None) -> tuple[TaskResult, UserDataModel | None]:
        """Read logged in users names"""
        users = []
        # Windows
        if self.system_info.os_family == OSFamily.WINDOWS:
            res = self._run_sut_cmd("query user")
            if res.exit_code == 0:
                lines = res.stdout.splitlines()
                # Skip the header line and extract usernames
                for line in lines[1:]:
                    columns = re.split(r"\s+", line.strip())  # Split based on whitespace
                    username = re.sub(r"^>", "", columns[0])  # Remove '>' if present
                    users.append(username)
            else:
                self._handle_command_failure(res)
                return self.result, None
        # Linux
        else:
            res = self._run_sut_cmd("who", sudo=True)
            if res.exit_code == 0:
                lines = res.stdout.splitlines()
                for line in lines:
                    columns = line.split()
                    users.append(columns[0])
            else:
                self._handle_command_failure(res)
                return self.result, None

        user_data = UserDataModel(active_users=users)
        self._log_event(
            category="USER_READ",
            description="User data collected",
            data=user_data.model_dump(),
            priority=EventPriority.INFO,
        )
        self.result.message = f"Users: {users}"
        self.result.status = ExecutionStatus.OK
        return self.result, user_data
