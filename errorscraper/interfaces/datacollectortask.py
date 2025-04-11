# Copyright (C) 2024 Advanced Micro Devices, Inc. All rights reserved.
import abc
import inspect
import logging
from functools import wraps
from typing import Callable, ClassVar, Generic, Optional, Type

from pydantic import ValidationError

from errorscraper.enums import (
    EventCategory,
    EventPriority,
    ExecutionStatus,
    SystemInteractionLevel,
)
from errorscraper.generictypes import TCollectArg, TDataModel
from errorscraper.interfaces.task import SystemCompatibilityError, Task
from errorscraper.models import DataModel, SystemInfo, TaskResult
from errorscraper.utils import get_exception_details, get_exception_traceback

from .connectionmanager import TConnection
from .taskhook import TaskHook


def collect_decorator(
    func: Callable[..., tuple[TaskResult, TDataModel | None]],
) -> Callable[..., tuple[TaskResult, TDataModel | None]]:
    @wraps(func)
    def wrapper(
        collector: "DataCollector", args: Optional[TCollectArg]
    ) -> tuple[TaskResult, TDataModel | None]:
        collector.logger.info("Running data collector: %s", collector.__class__.__name__)
        collector.result = collector._init_result()
        try:
            result, data = func(collector, args)
        except Exception as exception:
            if isinstance(exception, ValidationError):
                collector._log_event(
                    category=EventCategory.RUNTIME,
                    description="Pydantic validation error",
                    data=get_exception_details(exception),
                    priority=EventPriority.CRITICAL,
                    console_log=True,
                )
            else:
                collector._log_event(
                    category=EventCategory.RUNTIME,
                    description=f"Exception: {str(exception)}",
                    data=get_exception_traceback(exception),
                    priority=EventPriority.CRITICAL,
                    console_log=True,
                )
            collector.result.status = ExecutionStatus.EXECUTION_FAILURE
            result = collector.result
            data = None

        if data is None and not result.status:
            result.status = ExecutionStatus.EXECUTION_FAILURE

        result.finalize()

        collector._run_hooks(result, data=data)

        return result, data

    return wrapper


class DataCollector(Task, abc.ABC, Generic[TConnection, TDataModel, TCollectArg]):
    """Parent class for all data collectors"""

    TASK_TYPE = "DATA_COLLECTOR"

    DATA_MODEL: Type[TDataModel]

    # A set of supported SKUs for this data collector
    SUPPORTED_SKUS: ClassVar[Optional[set[str]]] = None

    # A set of supported Platforms for this data collector,
    SUPPORTED_PLATFORMS: ClassVar[Optional[set[str]]] = None

    def __init__(
        self,
        system_info: SystemInfo,
        connection: TConnection,
        logger: Optional[logging.Logger] = None,
        system_interaction_level: SystemInteractionLevel | str = SystemInteractionLevel.STANDARD,
        max_event_priority_level: EventPriority | str = EventPriority.CRITICAL,
        parent: Optional[str] = None,
        task_hooks: Optional[list[TaskHook]] = None,
        **kwargs,
    ):
        """data collector init function

        Args:
            system_info (SystemInfo): system info object for target system for data collection
            system_interaction (SystemInteraction): enum to indicate the type of actions that can be performed when interacting with the system
            event_reporter (str, optional): Described the reporter of the event. Defaults to DEFAULT_EVENT_REPORTER.
            logger (Optional[logging.Logger], optional): python logger object. Defaults to None.
            log_path (Optional[str], optional): file system log path. Defaults to None.
        """
        super().__init__(
            system_info=system_info,
            logger=logger,
            max_event_priority_level=max_event_priority_level,
            parent=parent,
            task_hooks=task_hooks,
        )

        if isinstance(system_interaction_level, str):
            system_interaction_level = getattr(SystemInteractionLevel, system_interaction_level)

        self.system_interaction_level = system_interaction_level
        self.connection = connection

        if self.SUPPORTED_SKUS and self.system_info.sku not in self.SUPPORTED_SKUS:
            raise SystemCompatibilityError(
                f"{self.system_info.sku} SKU is not supported for this collector"
            )
        if self.SUPPORTED_PLATFORMS and self.system_info.platform not in self.SUPPORTED_PLATFORMS:
            raise SystemCompatibilityError(
                f"{self.system_info.platform} platform is not supported for this collector"
            )

    def __init_subclass__(cls, **kwargs) -> None:
        super().__init_subclass__(**kwargs)
        if not inspect.isabstract(cls):
            if not hasattr(cls, "DATA_MODEL"):
                raise TypeError(f"No data model set for {cls.__name__}")
            if not issubclass(cls.DATA_MODEL, DataModel):
                raise TypeError(f"DATA_MODEL must be a subclass of DataModel in {cls.__name__}")
        if hasattr(cls, "collect_data"):
            cls.collect_data = collect_decorator(cls.collect_data)
        else:
            raise TypeError(f"Data collector {cls.__name__} must implement collect_data")

    @abc.abstractmethod
    def collect_data(
        self, args: Optional[TCollectArg] = None
    ) -> tuple[TaskResult, TDataModel | None]:
        """Collect data from a target system

        Returns:
            tuple[TaskResult, DataModel]: tuple containing result and data model
        """
