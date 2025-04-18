from errorscraper.base import InBandDataCollector
from errorscraper.connection.inband import CommandArtifact
from errorscraper.enums import EventCategory, EventPriority, ExecutionStatus, OSFamily
from errorscraper.models import TaskResult

from .authlogdata import AuthLogDataModel


class AuthLogCollector(InBandDataCollector[AuthLogDataModel]):
    """Collect authentication/security related history in the respective log files

    Debian/Ubuntu: /var/log/auth.log
    RHEL/CentOS: /var/log/secure

    """

    SUPPORTED_OS_FAMILY: set[OSFamily] = {OSFamily.LINUX}

    DATA_MODEL = AuthLogDataModel

    AUTH_LOG_PATH = "/var/log/auth.log"

    SECURE_LOG_PATH = "/var/log/secure"

    def _handle_command_failure(self, command_artifact: CommandArtifact, log_name: str | None):
        self._log_event(
            category=EventCategory.OS,
            description=f"Error running command: {command_artifact.command}",
            priority=EventPriority.WARNING,
            data={
                "stderr": command_artifact.stderr,
                "exit_code": command_artifact.exit_code,
            },
        )
        self.result.message = (
            f"Failed to read {log_name} file"
            if log_name
            else f"{self.AUTH_LOG_PATH} or {self.SECURE_LOG_PATH} not found"
        )
        self.result.status = ExecutionStatus.NOT_RAN

    def collect_data(self, args=None) -> tuple[TaskResult, AuthLogDataModel | None]:
        """Check if /var/log/auth.log or /var/log/secure file exists and read its content"""
        log_name = None

        # check if /var/log/auth.log file exists
        auth_log_exists = self._run_sut_cmd(
            f"test -f {self.AUTH_LOG_PATH}", sudo=True, log_artifact=False
        )

        if auth_log_exists.exit_code == 0:
            res = self._run_sut_cmd(f"cat {self.AUTH_LOG_PATH}", sudo=True, log_artifact=False)
            log_name = self.AUTH_LOG_PATH
            if res.exit_code == 0:
                log_content = res.stdout
            else:
                self._handle_command_failure(command_artifact=res, log_name=log_name)
                return self.result, None

        # No auth.log exists, check if /var/log/secure file exists
        else:
            secure_log_exists = self._run_sut_cmd(
                f"test -f {self.SECURE_LOG_PATH}", sudo=True, log_artifact=False
            )

            if secure_log_exists.exit_code == 0:
                res = self._run_sut_cmd(
                    f"cat {self.SECURE_LOG_PATH}", sudo=True, log_artifact=False
                )
                log_name = self.SECURE_LOG_PATH
                if res.exit_code == 0:
                    log_content = res.stdout
                else:
                    self._handle_command_failure(command_artifact=res, log_name=log_name)
                    return self.result, None

            # neither auth.log nor secure log exists
            else:
                self._handle_command_failure(command_artifact=secure_log_exists, log_name=None)
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

        log_data = AuthLogDataModel(log_content=log_content)
        self._log_event(
            category=EventCategory.OS,
            description=f"{log_name} data collected",
            priority=EventPriority.INFO,
        )
        self.result.message = f"{log_name} data collected"
        self.result.status = ExecutionStatus.OK

        return self.result, log_data
