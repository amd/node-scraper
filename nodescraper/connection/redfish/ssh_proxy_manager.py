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

from ..inband.inbandremote import RemoteShell, SSHConnectionError
from .redfish_connection import RedfishConnectionError
from .redfish_manager import _build_base_url
from .ssh_proxy_connection import SshProxyRedfishConnection
from .ssh_proxy_params import RedfishSshProxyConnectionParams


class RedfishSshProxyConnectionManager(
    ConnectionManager[SshProxyRedfishConnection, RedfishSshProxyConnectionParams]
):
    """SSH to a BMC and curl Redfish on an address reachable only from that host (AMC)."""

    def __init__(
        self,
        system_info: SystemInfo,
        logger: Optional[Logger] = None,
        max_event_priority_level: Union[EventPriority, str] = EventPriority.CRITICAL,
        parent: Optional[str] = None,
        task_result_hooks: Optional[list[TaskResultHook]] = None,
        connection_args: Optional[RedfishSshProxyConnectionParams] = None,
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
        """Open BMC SSH and verify AMC Redfish via curl.

        Returns:
            TaskResult for the connection attempt.
        """
        if not self.connection_args:
            self._log_event(
                category=EventCategory.RUNTIME,
                description="No Redfish SSH-proxy connection parameters provided",
                priority=EventPriority.CRITICAL,
                console_log=True,
            )
            self.result.status = ExecutionStatus.EXECUTION_FAILURE
            return self.result

        raw = self.connection_args
        if isinstance(raw, dict):
            params = RedfishSshProxyConnectionParams.model_validate(raw)
        elif isinstance(raw, RedfishSshProxyConnectionParams):
            params = raw
        else:
            self._log_event(
                category=EventCategory.RUNTIME,
                description=(
                    "Redfish SSH-proxy connection_args must be dict or "
                    "RedfishSshProxyConnectionParams"
                ),
                priority=EventPriority.CRITICAL,
                console_log=True,
            )
            self.result.status = ExecutionStatus.EXECUTION_FAILURE
            return self.result

        base_url = _build_base_url(str(params.host), params.port, params.use_https)
        shell: Optional[RemoteShell] = None
        try:
            self.logger.info(
                "Connecting SSH proxy Redfish: ssh=%s curl=%s",
                params.ssh.hostname,
                base_url,
            )
            shell = RemoteShell(params.ssh)
            shell.connect_ssh()
            conn = SshProxyRedfishConnection(
                shell=shell,
                base_url=base_url,
                timeout=params.timeout_seconds,
                api_root=params.api_root,
            )
            conn.get_service_root()
            self.connection = conn
        except SSHConnectionError as exc:
            self._log_event(
                category=EventCategory.SSH,
                description=str(exc),
                priority=EventPriority.CRITICAL,
                console_log=True,
            )
            self.result.status = ExecutionStatus.EXECUTION_FAILURE
            self.connection = None
            if shell is not None:
                try:
                    shell.client.close()
                except Exception:
                    pass
        except RedfishConnectionError as exc:
            self._log_event(
                category=EventCategory.RUNTIME,
                description=str(exc),
                priority=EventPriority.CRITICAL,
                console_log=True,
            )
            self.result.status = ExecutionStatus.EXECUTION_FAILURE
            self.connection = None
            if shell is not None:
                try:
                    shell.client.close()
                except Exception:
                    pass
        except Exception as exc:
            self._log_event(
                category=EventCategory.RUNTIME,
                description=f"Redfish SSH-proxy connection failed: {exc}",
                data=get_exception_traceback(exc),
                priority=EventPriority.CRITICAL,
                console_log=True,
            )
            self.result.status = ExecutionStatus.EXECUTION_FAILURE
            self.connection = None
            if shell is not None:
                try:
                    shell.client.close()
                except Exception:
                    pass
        return self.result

    def disconnect(self) -> None:
        """Close the curl wrapper and the BMC SSH session."""
        conn = self.connection
        if isinstance(conn, SshProxyRedfishConnection):
            conn.close()
            try:
                conn._shell.client.close()
            except Exception:
                pass
        super().disconnect()
