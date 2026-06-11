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
from typing import Optional, Union

from nodescraper.enums import EventCategory, EventPriority, ExecutionStatus
from nodescraper.interfaces.connectionmanager import ConnectionManager
from nodescraper.interfaces.taskresulthook import TaskResultHook
from nodescraper.models import SystemInfo, TaskResult
from nodescraper.utils import get_exception_traceback

from ..inband.inband import InBandConnection
from ..inband.inbandremote import RemoteShell, SSHConnectionError
from ..redfish.redfish_params import RedfishConnectionParams, redfish_params_to_ssh


class OobSshConnectionManager(ConnectionManager[InBandConnection, RedfishConnectionParams]):
    """SSH to the BMC using the same host and credentials as Redfish (OOB shell)."""

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
            self._log_event(
                category=EventCategory.RUNTIME,
                description="No Redfish connection parameters provided for OOB SSH",
                priority=EventPriority.CRITICAL,
                console_log=True,
            )
            self.result.status = ExecutionStatus.EXECUTION_FAILURE
            return self.result

        raw = self.connection_args
        if isinstance(raw, dict):
            params = RedfishConnectionParams.model_validate(raw)
        elif isinstance(raw, RedfishConnectionParams):
            params = raw
        else:
            self._log_event(
                category=EventCategory.RUNTIME,
                description="Redfish connection_args must be dict or RedfishConnectionParams",
                priority=EventPriority.CRITICAL,
                console_log=True,
            )
            self.result.status = ExecutionStatus.EXECUTION_FAILURE
            return self.result

        try:
            ssh_params = redfish_params_to_ssh(params)
            self.logger.info("Initializing OOB SSH to BMC host %s", ssh_params.hostname)
            self.connection = RemoteShell(ssh_params)
            self.connection.connect_ssh()
        except SSHConnectionError as exception:
            self._log_event(
                category=EventCategory.SSH,
                description=str(exception),
                priority=EventPriority.CRITICAL,
                console_log=True,
            )
            self.result.status = ExecutionStatus.EXECUTION_FAILURE
            self.connection = None
        except Exception as exception:
            self._log_event(
                category=EventCategory.SSH,
                description=f"Exception during OOB SSH: {exception!s}",
                data=get_exception_traceback(exception),
                priority=EventPriority.CRITICAL,
                console_log=True,
            )
            self.result.status = ExecutionStatus.EXECUTION_FAILURE
            self.connection = None
        return self.result

    def disconnect(self) -> None:
        conn = self.connection
        super().disconnect()
        if isinstance(conn, RemoteShell):
            try:
                conn.client.close()
            except Exception:
                pass
