###############################################################################
#
# MIT License
#
# Copyright (c) 2026 Advanced Micro Devices, Inc.
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
from typing import ClassVar, Optional, Union

from nodescraper.enums import EventCategory, EventPriority, ExecutionStatus
from nodescraper.interfaces.connectionmanager import ConnectionManager
from nodescraper.interfaces.taskresulthook import TaskResultHook
from nodescraper.models import SystemInfo, TaskResult

from ..inband.inband import InBandConnection
from ..inband.inbandremote import RemoteShell, SSHConnectionError
from ..redfish.redfish_params import RedfishConnectionParams, redfish_params_to_ssh


class OobSshConnectionManager(ConnectionManager[InBandConnection, RedfishConnectionParams]):
    """SSH to the BMC using the same host and credentials as Redfish (OOB shell)."""

    CONNECTION_ARGS_MODEL: ClassVar[type[RedfishConnectionParams]] = RedfishConnectionParams

    def __init__(
        self,
        system_info: SystemInfo,
        logger: Optional[Logger] = None,
        max_event_priority_level: Union[EventPriority, str] = EventPriority.CRITICAL,
        parent: Optional[str] = None,
        task_result_hooks: Optional[list[TaskResultHook]] = None,
        connection_args: Optional[RedfishConnectionParams] = None,
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

    def connect(self) -> TaskResult:
        if not self.connection_args:
            return self._fail_connect(
                EventCategory.RUNTIME, "No Redfish connection parameters provided for OOB SSH"
            )

        raw = self.connection_args
        if isinstance(raw, dict):
            try:
                params = RedfishConnectionParams.model_validate(raw)
            except ValueError as exception:
                return self._fail_connect(
                    EventCategory.RUNTIME, f"Invalid Redfish connection parameters: {exception}"
                )
        elif isinstance(raw, RedfishConnectionParams):
            params = raw
        else:
            return self._fail_connect(
                EventCategory.RUNTIME,
                "Redfish connection_args must be dict or RedfishConnectionParams",
            )

        if params.is_multi_target and params.host is None:
            message = (
                "OOB SSH plugins use a single BMC host. "
                "A targets list applies only to Redfish plugins."
            )
            self._log_event(
                category=EventCategory.RUNTIME,
                description=message,
                priority=EventPriority.WARNING,
                console_log=True,
            )
            self.result.status = ExecutionStatus.NOT_RAN
            self.result.message = message
            return self.result

        try:
            ssh_params = redfish_params_to_ssh(params)
        except ValueError as exception:
            return self._fail_connect(
                EventCategory.RUNTIME, f"Invalid OOB SSH connection parameters: {exception}"
            )

        hostname = ssh_params.hostname
        self.logger.info("Initializing OOB SSH to BMC host %s", hostname)
        shell = RemoteShell(ssh_params)
        try:
            shell.connect_ssh()
        except SSHConnectionError as exception:
            shell.client.close()
            return self._fail_connect(
                EventCategory.SSH, f"OOB SSH connection to BMC '{hostname}' failed: {exception}"
            )

        self.connection = shell
        return self.result

    def disconnect(self) -> None:
        conn = self.connection
        super().disconnect()
        if isinstance(conn, RemoteShell):
            try:
                conn.client.close()
            except Exception:
                pass
