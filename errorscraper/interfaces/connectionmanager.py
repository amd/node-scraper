# Copyright (C) 2024 Advanced Micro Devices, Inc. All rights reserved.
from __future__ import annotations

import abc
import logging
import types
from functools import wraps
from typing import Callable, Generic, Optional, TypeVar

from pydantic import BaseModel

from errorscraper.enums import EventCategory, EventPriority, ExecutionStatus
from errorscraper.models import SystemInfo, TaskResult
from errorscraper.utils import get_exception_traceback

from .task import Task
from .taskhook import TaskHook


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
TConnectArg = TypeVar("TConnectArg", bound="BaseModel")


class ConnectionManager(Task, Generic[TConnection, TConnectArg]):
    """Base class for all connection management tasks"""

    TASK_TYPE = "CONNECTION_MANAGER"

    def __init__(
        self,
        system_info: SystemInfo,
        logger: Optional[logging.Logger] = None,
        max_event_priority_level: EventPriority | str = EventPriority.CRITICAL,
        parent: Optional[str] = None,
        task_hooks: list[TaskHook] | types.NoneType = None,
        connection_args: Optional[TConnectArg | dict] = None,
        **kwargs,
    ):
        super().__init__(
            system_info=system_info,
            logger=logger,
            max_event_priority_level=max_event_priority_level,
            parent="CONNECTION" if not parent else parent,
            task_hooks=task_hooks,
            **kwargs,
        )

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
