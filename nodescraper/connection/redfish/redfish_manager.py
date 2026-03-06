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

from .redfish_connection import RedfishConnection, RedfishConnectionError
from .redfish_params import RedfishConnectionParams


def _build_base_url(host: str, port: Optional[int], use_https: bool) -> str:
    scheme = "https" if use_https else "http"
    host_str = str(host)
    if port is not None:
        return f"{scheme}://{host_str}:{port}"
    return f"{scheme}://{host_str}"


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
        """Connect to the Redfish service and perform a simple GET to verify."""
        if not self.connection_args:
            self._log_event(
                category=EventCategory.RUNTIME,
                description="No Redfish connection parameters provided",
                priority=EventPriority.CRITICAL,
                console_log=True,
            )
            self.result.status = ExecutionStatus.EXECUTION_FAILURE
            return self.result

        # Accept dict from JSON config; convert to RedfishConnectionParams
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

        password = params.password.get_secret_value() if params.password else None
        base_url = _build_base_url(str(params.host), params.port, params.use_https)

        try:
            self.logger.info("Connecting to Redfish at %s", base_url)
            self.connection = RedfishConnection(
                base_url=base_url,
                username=params.username,
                password=password,
                timeout=params.timeout_seconds,
                use_session_auth=params.use_session_auth,
                verify_ssl=params.verify_ssl,
            )
            self.connection._ensure_session()
            self.connection.get_service_root()
        except RedfishConnectionError as exc:
            self._log_event(
                category=EventCategory.RUNTIME,
                description=f"Redfish connection error: {exc}",
                data=get_exception_traceback(exc) if exc.response is None else None,
                priority=EventPriority.CRITICAL,
                console_log=True,
            )
            self.result.status = ExecutionStatus.EXECUTION_FAILURE
            self.connection = None
        except Exception as exc:
            self._log_event(
                category=EventCategory.RUNTIME,
                description=f"Redfish connection failed: {exc}",
                data=get_exception_traceback(exc),
                priority=EventPriority.CRITICAL,
                console_log=True,
            )
            self.result.status = ExecutionStatus.EXECUTION_FAILURE
            self.connection = None
        return self.result

    def disconnect(self) -> None:
        """Disconnect and release the Redfish session."""
        if self.connection is not None:
            self.connection.close()
        super().disconnect()
