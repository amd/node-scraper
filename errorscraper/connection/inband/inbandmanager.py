from __future__ import annotations

from logging import Logger

from errorscraper.enums import (
    EventCategory,
    EventPriority,
    ExecutionStatus,
    OSFamily,
    SystemLocation,
)
from errorscraper.interfaces.connectionmanager import ConnectionManager
from errorscraper.interfaces.taskresulthook import TaskResultHook
from errorscraper.models import SystemInfo, TaskResult
from errorscraper.utils import get_exception_traceback

from .inband import InBandConnection
from .inbandlocal import LocalShell
from .inbandremote import RemoteShell
from .sshparams import SSHConnectionParams


class InBandConnectionManager(ConnectionManager[InBandConnection, SSHConnectionParams]):

    def __init__(
        self,
        system_info: SystemInfo,
        logger: Logger | None = None,
        max_event_priority_level: EventPriority | str = EventPriority.CRITICAL,
        parent: str | None = None,
        task_result_hooks: list[TaskResultHook] | None = None,
        connection_args: SSHConnectionParams | None = None,
        **kwargs,
    ):
        super().__init__(
            system_info,
            logger,
            max_event_priority_level,
            parent,
            task_result_hooks,
            connection_args,
            **kwargs,
        )

    def _check_os_family(self):
        if not self.connection:
            raise RuntimeError("Connection not initialized")

        self.logger.info("Checking OS family")
        res = self.connection.run_command("uname -s")
        if "not recognized as an internal or external command" in res.stdout + res.stderr:
            self.system_info.os_family = OSFamily.WINDOWS
        elif res.exit_code == 0:
            self.system_info.os_family = OSFamily.LINUX
        else:
            self._log_event(
                category=EventCategory.UNKNOWN,
                description="Unable to determine SUT OS",
                priority=EventPriority.WARNING,
            )
        self.logger.info("OS Family: %s", self.system_info.os_family.name)

    def connect(
        self,
    ) -> TaskResult:
        if self.system_info.location == SystemLocation.LOCAL:
            self.logger.info("Using local shell")
            self.connection = LocalShell()
            self._check_os_family()
            return self.result

        if not self.connection_args or not isinstance(self.connection_args, SSHConnectionParams):
            if not self.connection_args:
                message = "No SSH credentials provided"
            else:
                message = "Invalide SSH creddentials provided"

            self._log_event(
                category=EventCategory.RUNTIME,
                description=message,
                priority=EventPriority.CRITICAL,
                console_log=True,
            )
            self.result.status = ExecutionStatus.EXECUTION_FAILURE
            return self.result

        try:
            self.logger.info("Initializing SSH connection to system")
            self.connection = RemoteShell(self.connection_args)
            self.connection.connect_ssh()
            self._check_os_family()
        except Exception as exception:
            self._log_event(
                category=EventCategory.SSH,
                description=f"Exception during SSH: {str(exception)}",
                data=get_exception_traceback(exception),
                priority=EventPriority.CRITICAL,
                console_log=True,
            )
        return self.result

    def disconnect(self):
        super().disconnect()
        if isinstance(self.connection, RemoteShell):
            self.connection.client.close()
