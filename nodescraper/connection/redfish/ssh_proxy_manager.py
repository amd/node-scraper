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
from .redfish_manager import MultiTargetRedfishConnection, _build_base_url
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
            TaskResult: Connection result. One failed target is a warning when another connects.
        """
        params = self._validated_params()
        if params is None:
            return self.result
        if params.is_multi_target:
            return self._connect_multi(params)
        return self._connect_single(params)

    def _validated_params(self) -> Optional[RedfishSshProxyConnectionParams]:
        """Return connection params or record a failure when they are missing.

        Returns:
            Optional[RedfishSshProxyConnectionParams]: Parsed params, or None when invalid.
        """
        if not self.connection_args:
            self._log_event(
                category=EventCategory.RUNTIME,
                description="No Redfish SSH-proxy connection parameters provided",
                priority=EventPriority.CRITICAL,
                console_log=True,
            )
            self.result.status = ExecutionStatus.EXECUTION_FAILURE
            return None

        raw = self.connection_args
        if isinstance(raw, dict):
            return RedfishSshProxyConnectionParams.model_validate(raw)
        if isinstance(raw, RedfishSshProxyConnectionParams):
            return raw
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
        return None

    def _connect_single(self, params: RedfishSshProxyConnectionParams) -> TaskResult:
        """Connect one BMC SSH proxy.

        Args:
            params: Single-target SSH-proxy parameters.

        Returns:
            TaskResult: Connection result.
        """
        try:
            self.connection = self._open_proxy(params)
        except SSHConnectionError as exc:
            self._log_event(
                category=EventCategory.SSH,
                description=str(exc),
                priority=EventPriority.CRITICAL,
                console_log=True,
            )
            self.result.status = ExecutionStatus.EXECUTION_FAILURE
            self.connection = None
        except RedfishConnectionError as exc:
            self._log_event(
                category=EventCategory.RUNTIME,
                description=str(exc),
                priority=EventPriority.CRITICAL,
                console_log=True,
            )
            self.result.status = ExecutionStatus.EXECUTION_FAILURE
            self.connection = None
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
        return self.result

    def _connect_multi(self, params: RedfishSshProxyConnectionParams) -> TaskResult:
        """Connect each SSH-proxy target. One failure does not drop the others.

        Args:
            params: Parameters whose targets list is set.

        Returns:
            TaskResult: Warning when any target connects, execution failure when none do.
        """
        self.target_connections: dict[str, SshProxyRedfishConnection] = {}
        failed_targets: dict[str, str] = {}
        for target in params.targets or []:
            key, conn, error = self._connect_target(target)
            if conn is None:
                failed_targets[key] = error or f"SSH-proxy connection failed for target {key!r}"
                continue
            if key in self.target_connections:
                self._log_event(
                    category=EventCategory.RUNTIME,
                    description=(
                        f"Duplicate SSH-proxy target key {key!r}; keeping the first connection"
                    ),
                    priority=EventPriority.WARNING,
                    console_log=True,
                )
                self._close_proxy(conn)
                continue
            self.target_connections[key] = conn
        if not self.target_connections:
            self.result.status = ExecutionStatus.EXECUTION_FAILURE
            lines = "\n".join(f"[{k}] {v}" for k, v in failed_targets.items())
            self.result.message = f"SSH-proxy Redfish connection failed for every target\n{lines}"
            self.result.events.clear()
            return self.result
        if failed_targets:
            lines = "\n".join(f"[{k}] {v}" for k, v in failed_targets.items())
            self.result.status = ExecutionStatus.WARNING
            self.result.message = f"Some SSH-proxy Redfish targets failed to connect\n{lines}"
            # Clear events so TaskResult.finalize() does not re-append them as
            # "(N warnings: ...)" on the same line — the info is already in result.message.
            self.result.events.clear()
        self.connection = MultiTargetRedfishConnection(  # type: ignore[assignment]
            self.target_connections,
            max_workers=params.max_workers,
            failed_targets=failed_targets,
        )
        return self.result

    def _connect_target(
        self, target: RedfishSshProxyConnectionParams
    ) -> tuple[str, Optional[SshProxyRedfishConnection], Optional[str]]:
        """Connect one target and keep going when it fails.

        Args:
            target: SSH-proxy parameters for a single BMC.

        Returns:
            tuple[str, Optional[SshProxyRedfishConnection], Optional[str]]: Key, connection, and error.
        """
        key = _proxy_target_key(target)
        try:
            return key, self._open_proxy(target), None
        except Exception as exc:  # noqa: BLE001
            description = f"SSH-proxy Redfish connection failed for target {key!r}: {exc}"
            self._log_event(
                category=EventCategory.RUNTIME,
                description=description,
                priority=EventPriority.WARNING,
                console_log=True,
            )
            return key, None, description

    def _open_proxy(self, params: RedfishSshProxyConnectionParams) -> SshProxyRedfishConnection:
        """Open one BMC SSH session and verify the AMC Redfish root.

        Args:
            params: Single-target SSH-proxy parameters.

        Returns:
            SshProxyRedfishConnection: Open connection.

        Raises:
            ValueError: When host or ssh is missing.
        """
        if params.host is None or params.ssh is None:
            raise ValueError("SSH-proxy target requires host and ssh")
        base_url = _build_base_url(str(params.host), params.port, params.use_https)
        self.logger.info(
            "Connecting SSH proxy Redfish: ssh=%s curl=%s",
            params.ssh.hostname,
            base_url,
        )
        shell = RemoteShell(params.ssh)
        conn: Optional[SshProxyRedfishConnection] = None
        try:
            shell.connect_ssh()
            conn = SshProxyRedfishConnection(
                shell=shell,
                base_url=base_url,
                timeout=params.timeout_seconds,
                api_root=params.api_root,
            )
            conn.get_service_root()
            return conn
        except Exception:
            if conn is not None:
                self._close_proxy(conn)
            else:
                try:
                    shell.client.close()
                except Exception:
                    pass
            raise

    @staticmethod
    def _close_proxy(conn: SshProxyRedfishConnection) -> None:
        """Close the curl wrapper and the BMC SSH session.

        Args:
            conn: SSH-proxy Redfish connection to close.

        Returns:
            None.
        """
        conn.close()
        try:
            conn._shell.client.close()
        except Exception:
            pass

    def disconnect(self) -> None:
        """Close every SSH-proxy session and keep collected multi-target data."""
        conn = self.connection
        if isinstance(conn, MultiTargetRedfishConnection):
            self._multi_target_data: dict = dict(conn.multi_target_data)
            for target_conn in conn.target_connections.values():
                if isinstance(target_conn, SshProxyRedfishConnection):
                    self._close_proxy(target_conn)
                else:
                    target_conn.close()
            self.target_connections = {}
        elif isinstance(conn, SshProxyRedfishConnection):
            self._close_proxy(conn)
        super().disconnect()


def _proxy_target_key(target: RedfishSshProxyConnectionParams) -> str:
    """Return the target key, falling back to the SSH hostname.

    Args:
        target: One SSH-proxy target.

    Returns:
        str: target_key, otherwise the SSH hostname, otherwise the AMC host.
    """
    if target.target_key:
        return target.target_key
    if target.ssh is not None:
        return str(target.ssh.hostname)
    return str(target.host)
