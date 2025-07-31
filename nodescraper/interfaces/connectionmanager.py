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

import abc
import logging
import types
from functools import wraps
from typing import Callable, Generic, Optional, TypeVar

from pydantic import BaseModel

from nodescraper.enums import EventCategory, EventPriority, ExecutionStatus
from nodescraper.models import SystemInfo, TaskResult
from nodescraper.typeutils import TypeUtils
from nodescraper.utils import get_exception_traceback

from .task import Task
from .taskresulthook import TaskResultHook


def connect_decorator(func: Callable[..., TaskResult]) -> Callable[..., TaskResult]:
    @wraps(func)
    def wrapper(
        connection_manager: "ConnectionManager",
        **kwargs,
    ) -> TaskResult:
        connection_manager.logger.info(
            "Initializing connection: %s", connection_manager.__class__.__name__
        )
        connection_manager.result = connection_manager._init_result()

        try:
            result = func(connection_manager, **kwargs)
        except Exception as exception:
            connection_manager._log_event(
                category=EventCategory.RUNTIME,
                description=f"Exception: {str(exception)}",
                data=get_exception_traceback(exception),
                priority=EventPriority.CRITICAL,
                console_log=True,
            )
            connection_manager.result.status = ExecutionStatus.EXECUTION_FAILURE
            result = connection_manager.result

        result.finalize()

        connection_manager._run_hooks(result)

        return result

    return wrapper


TConnection = TypeVar("TConnection")
TConnectionManager = TypeVar("TConnectionManager", bound="ConnectionManager")
TConnectArg = TypeVar("TConnectArg", bound="Optional[BaseModel]")


class ConnectionManager(Task, Generic[TConnection, TConnectArg]):
    """Base class for all connection management tasks"""

    TASK_TYPE = "CONNECTION_MANAGER"

    def __init__(
        self,
        system_info: SystemInfo,
        logger: Optional[logging.Logger] = None,
        max_event_priority_level: EventPriority | str = EventPriority.CRITICAL,
        parent: Optional[str] = None,
        task_result_hooks: list[TaskResultHook] | types.NoneType = None,
        connection_args: Optional[TConnectArg | dict] = None,
        **kwargs,
    ):
        super().__init__(
            system_info=system_info,
            logger=logger,
            max_event_priority_level=max_event_priority_level,
            parent="connection" if not parent else parent,
            task_result_hooks=task_result_hooks,
            **kwargs,
        )

        if isinstance(connection_args, dict):
            generic_map = TypeUtils.get_generic_map(self.__class__)
            connection_arg_model = generic_map.get(TConnectArg)
            if not connection_arg_model:
                raise ValueError("No model defined for connection args")

            connection_args = connection_arg_model(**connection_args)

        self.connection_args = connection_args
        self.connection: TConnection | None = None

    def __init_subclass__(cls, **kwargs) -> None:
        super().__init_subclass__(**kwargs)

        if hasattr(cls, "connect"):
            cls.connect = connect_decorator(cls.connect)

    def __enter__(self):
        """Context manager enter"""
        return self

    def __exit__(
        self,
        _exc_type: type[Exception],
        _exc_value: Exception,
        traceback: types.TracebackType,
    ):
        self.disconnect()

    @abc.abstractmethod
    def connect(self) -> TaskResult:
        """initialize connection"""

    def disconnect(self):
        """disconnect connection (Optional)"""
        self.connection = None
        self.result.status = ExecutionStatus.UNSET
