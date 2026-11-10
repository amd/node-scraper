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
from nodescraper.utils import get_exception_traceback

from .oob_rest_connection import OobRestConnection
from .oob_rest_params import OobRestConnectionParams


class OobRestConnectionManager(ConnectionManager[OobRestConnection, OobRestConnectionParams]):
    """Connection manager for a generic out-of-band REST controller.

    Builds an :class:`OobRestConnection` from the provided parameters and
    authenticates once on connect, so a controller that is unreachable or
    rejects credentials fails here rather than in every plugin in turn.
    """

    CONNECTION_ARGS_MODEL: ClassVar[type[OobRestConnectionParams]] = OobRestConnectionParams

    def __init__(
        self,
        system_info: SystemInfo,
        logger: Optional[Logger] = None,
        max_event_priority_level: Union[EventPriority, str] = EventPriority.CRITICAL,
        parent: Optional[str] = None,
        task_result_hooks: Optional[list[TaskResultHook]] = None,
        connection_args: Optional[OobRestConnectionParams] = None,
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
                description="No OOB REST connection parameters provided",
                priority=EventPriority.CRITICAL,
                console_log=True,
            )
            self.result.status = ExecutionStatus.EXECUTION_FAILURE
            return self.result

        raw = self.connection_args
        if isinstance(raw, dict):
            params = OobRestConnectionParams.model_validate(raw)
        elif isinstance(raw, OobRestConnectionParams):
            params = raw
        else:
            self._log_event(
                category=EventCategory.RUNTIME,
                description="OOB REST connection_args must be dict or OobRestConnectionParams",
                priority=EventPriority.CRITICAL,
                console_log=True,
            )
            self.result.status = ExecutionStatus.EXECUTION_FAILURE
            return self.result

        try:
            self.logger.info("Initializing OOB REST connection to %s", params.host)
            connection = OobRestConnection(params)
            connection.authenticate()
            self.connection = connection
        except Exception as exception:
            self._log_event(
                category=EventCategory.NETWORK,
                description=f"Exception during OOB REST connection: {exception!s}",
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
        if isinstance(conn, OobRestConnection):
            try:
                conn.close()
            except Exception:
                pass
