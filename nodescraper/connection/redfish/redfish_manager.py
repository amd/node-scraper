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
from typing import Any, Mapping, Optional, Union

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

    def __init__(
        self,
        target_connections: Mapping[str, RedfishConnection],
        max_workers: Optional[int] = None,
        failed_targets: Optional[dict[str, str]] = None,
    ) -> None:
        self.target_connections = dict(target_connections)
        self.multi_target_data: dict[str, Any] = {}
        self.max_workers = max_workers
        self.failed_targets = dict(failed_targets or {})


def collected_multi_target_data(connection_manager: Any) -> dict[str, Any]:
    """Return per-target data from an open connection or from the copy made at disconnect.

    Args:
        connection_manager: Redfish connection manager for this plugin.

    Returns:
        dict[str, Any]: Target key to collected data. Empty for single-target runs.
    """
    conn = getattr(connection_manager, "connection", None)
    if isinstance(conn, MultiTargetRedfishConnection) and conn.multi_target_data:
        return conn.multi_target_data
    return getattr(connection_manager, "_multi_target_data", None) or {}


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
            failed_targets: dict[str, str] = {}
            for target in params.targets:  # type: ignore[union-attr]
                key, conn, error = self._connect_target(target)
                if conn is None:
                    failed_targets[key] = error or f"Redfish connection failed for target {key!r}"
                    continue
                if key in self.target_connections:
                    self._log_event(
                        category=EventCategory.RUNTIME,
                        description=f"Duplicate Redfish target key {key!r}; keeping the first connection",
                        priority=EventPriority.WARNING,
                        console_log=True,
                    )
                    conn.close()
                    continue
                self.target_connections[key] = conn
            if not self.target_connections:
                self.result.status = ExecutionStatus.EXECUTION_FAILURE
                self.result.message = "Redfish connection failed for every target"
            else:
                # Set self.connection so DataPlugin.collect() does not short-circuit.
                self.connection = MultiTargetRedfishConnection(  # type: ignore[assignment]
                    self.target_connections,
                    max_workers=params.max_workers,
                    failed_targets=failed_targets,
                )
            return self.result

        return self._connect_single(params)

    def _connect_target(
        self, target: RedfishConnectionParams
    ) -> tuple[str, Optional[RedfishConnection], Optional[str]]:
        """Connect one target.

        Args:
            target: Connection parameters for a single BMC.

        Returns:
            tuple[str, Optional[RedfishConnection], Optional[str]]: Target key, connection, and error text.
        """
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
            return key, conn, None
        except (RedfishConnectionError, Exception) as exc:  # noqa: BLE001
            description = f"Redfish connection failed for target {key!r}: {exc}"
            self._log_event(
                category=EventCategory.RUNTIME,
                description=description,
                priority=EventPriority.WARNING,
                console_log=True,
            )
            return key, None, description

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
        """Disconnect Redfish sessions and keep collected multi-target data on the manager."""
        if isinstance(self.connection, MultiTargetRedfishConnection):
            self._multi_target_data: dict[str, Any] = dict(self.connection.multi_target_data)
            for conn in self.connection.target_connections.values():
                conn.close()
            self.target_connections = {}
        elif self.connection is not None:
            self.connection.close()
        super().disconnect()
