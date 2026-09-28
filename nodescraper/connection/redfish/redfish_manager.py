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
from typing import Any, Optional, Union

from nodescraper.enums import EventCategory, EventPriority, ExecutionStatus
from nodescraper.interfaces.connectionmanager import ConnectionManager
from nodescraper.interfaces.taskresulthook import TaskResultHook
from nodescraper.models import SystemInfo, TaskResult

from .redfish_connection import RedfishConnection, RedfishConnectionError
from .redfish_params import RedfishConnectionParams


def _build_base_url(host: str, port: Optional[int], use_https: bool) -> str:
    scheme = "https" if use_https else "http"
    host_str = str(host)
    if port is not None:
        return f"{scheme}://{host_str}:{port}"
    return f"{scheme}://{host_str}"


class MultiTargetRedfishConnection:
    """Sentinel placed on RedfishConnectionManager.connection in multi-target mode.

    Carrying this object (rather than leaving connection=None) allows the standard
    DataPlugin.collect() guard to pass, while RedfishDataCollector's __init_subclass__
    wrapper intercepts collect_data and iterates the individual target connections.
    """

    def __init__(self, target_connections: dict[str, RedfishConnection]) -> None:
        self.target_connections = target_connections
        self.multi_target_data: dict[str, Any] = {}


class RedfishConnectionManager(ConnectionManager[RedfishConnection, RedfishConnectionParams]):
    """Connection manager for Redfish (BMC) API."""

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
        """Creates a RedfishConnectionManager Task instance.

        Args:
            system_info (SystemInfo): System information for the connection manager task.
            logger (Optional[logging.Logger], optional): _description_. Defaults to None.
            max_event_priority_level (Union[EventPriority, str], optional): _description_. Defaults to EventPriority.CRITICAL.
            parent (Optional[str], optional): _description_. Defaults to None.
            task_result_hooks (Optional[list[TaskResultHook], None], optional): _description_. Defaults to None.
            connection_args (Optional[Union[TConnectArg, dict]], optional): _description_. Defaults to None.
            kwargs (dict, optional): Additional keyword arguments passed to the parent class.

        Raises:
            ValueError: Will raise a ValueError when the connection_args cannot be mapped to the expected model.
        """
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
        """Connect to Redfish (single-target or multi-target)."""
        if not self.connection_args:
            self._log_event(
                category=EventCategory.RUNTIME,
                description="No Redfish connection parameters provided",
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

        if params.is_multi_target:
            self.target_connections: dict[str, RedfishConnection] = {}
            for target in params.targets:  # type: ignore[union-attr]
                key, conn = self._connect_target(target)
                if conn is not None:
                    self.target_connections[key] = conn
            if not self.target_connections:
                self.result.status = ExecutionStatus.EXECUTION_FAILURE
            else:
                # Set self.connection so DataPlugin.collect() does not short-circuit.
                self.connection = MultiTargetRedfishConnection(self.target_connections)  # type: ignore[assignment]
            return self.result

        return self._connect_single(params)

    def _connect_target(
        self, target: RedfishConnectionParams
    ) -> tuple[str, Optional[RedfishConnection]]:
        """Connect one target; returns (key, connection) or (key, None) on failure."""
        key = target.target_key or str(target.host)
        password = target.password.get_secret_value() if target.password else None
        base_url = _build_base_url(str(target.host), target.port, target.use_https)
        try:
            self.logger.info("Connecting to Redfish at %s (target=%r)", base_url, key)
            conn = RedfishConnection(
                base_url=base_url,
                username=target.username or "",
                password=password,
                timeout=target.timeout_seconds,
                use_session_auth=target.use_session_auth,
                verify_ssl=target.verify_ssl,
                api_root=target.api_root,
            )
            conn._ensure_session()
            conn.get_service_root()
            return key, conn
        except (RedfishConnectionError, Exception) as exc:  # noqa: BLE001
            self._log_event(
                category=EventCategory.RUNTIME,
                description=f"Redfish connection failed for target {key!r}: {exc}",
                priority=EventPriority.CRITICAL,
                console_log=True,
            )
            return key, None

    def _connect_single(self, params: RedfishConnectionParams) -> TaskResult:
        """Connect in single-target mode (original connect logic)."""
        password = params.password.get_secret_value() if params.password else None
        base_url = _build_base_url(str(params.host), params.port, params.use_https)
        try:
            self.logger.info("Connecting to Redfish at %s", base_url)
            self.connection = RedfishConnection(
                base_url=base_url,
                username=params.username or "",
                password=password,
                timeout=params.timeout_seconds,
                use_session_auth=params.use_session_auth,
                verify_ssl=params.verify_ssl,
                api_root=params.api_root,
            )
            self.connection._ensure_session()
            self.connection.get_service_root()
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
                description=f"Redfish connection failed: {exc}",
                priority=EventPriority.CRITICAL,
                console_log=True,
            )
            self.result.status = ExecutionStatus.EXECUTION_FAILURE
            self.connection = None
        return self.result

    def disconnect(self) -> None:
        """Disconnect all Redfish sessions, preserving multi-target data on the manager."""
        if isinstance(self.connection, MultiTargetRedfishConnection):
            # Persist collected data so analyze() can access it after disconnect.
            self._multi_target_data: dict[str, Any] = dict(self.connection.multi_target_data)
            for conn in self.connection.target_connections.values():
                conn.close()
        elif self.connection is not None:
            self.connection.close()
        for conn in getattr(self, "target_connections", {}).values():
            conn.close()
        self.target_connections = {}
        super().disconnect()
