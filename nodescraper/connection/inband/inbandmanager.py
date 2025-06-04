###############################################################################
#
# MIT License
#
# Copyright (c) 2025 Advanced Micro Devices, Inc.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
###############################################################################
from __future__ import annotations

from logging import Logger

from nodescraper.enums import (
    EventCategory,
    EventPriority,
    ExecutionStatus,
    OSFamily,
    SystemLocation,
)
from nodescraper.interfaces.connectionmanager import ConnectionManager
from nodescraper.interfaces.taskresulthook import TaskResultHook
from nodescraper.models import SystemInfo, TaskResult
from nodescraper.utils import get_exception_traceback

from .inband import InBandConnection
from .inbandlocal import LocalShell
from .inbandremote import RemoteShell, SSHConnectionError
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
        """Check the OS family of the system under test (SUT)

        Raises:
            RuntimeError: If the connection is not initialized
        """
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
        """Connect to the system under test (SUT) using in-band connection

        Returns:
            TaskResult: The result of the connection attempt
        """
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
        except SSHConnectionError as exception:
            self._log_event(
                category=EventCategory.SSH,
                description=f"{str(exception)}",
                priority=EventPriority.CRITICAL,
                console_log=True,
            )
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
        """Disconnect in-band connection"""
        super().disconnect()
        if isinstance(self.connection, RemoteShell):
            self.connection.client.close()
