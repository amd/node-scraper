# Copyright (C) 2024 Advanced Micro Devices, Inc. All rights reserved.
from __future__ import annotations

import abc
import inspect
from functools import wraps
from typing import Callable, Generic, Optional, Type

from pydantic import ValidationError

from errorscraper.enums import EventCategory, EventPriority, ExecutionStatus
from errorscraper.generictypes import TAnalyzeArg, TDataModel
from errorscraper.interfaces.task import Task
from errorscraper.models import TaskResult
from errorscraper.models.datamodel import DataModel
from errorscraper.utils import get_exception_traceback


def analyze_decorator(func: Callable[..., TaskResult]) -> Callable[..., TaskResult]:
    @wraps(func)
    def wrapper(
        analyzer: "DataAnalyzer",
        data: DataModel,
        args: Optional[TAnalyzeArg | dict] = None,
    ) -> TaskResult:
        analyzer.logger.info("Running data analyzer: %s", analyzer.__class__.__name__)
        analyzer.result = analyzer._init_result()

        if not isinstance(data, analyzer.DATA_MODEL):
            analyzer._log_event(
                category=EventCategory.RUNTIME,
                description="Analyzer passed invalid data",
                data={"data_type": type(data), "expected": analyzer.DATA_MODEL.__name__},
                priority=EventPriority.CRITICAL,
                console_log=True,
            )
            analyzer.result.message = "Invalid data input"
            analyzer.result.status = ExecutionStatus.EXECUTION_FAILURE
        else:
            try:
                if isinstance(args, dict):
                    # using Pydatinc model class
                    model_cls = func.__annotations__.get("args")
                    if isinstance(model_cls, type):
                        args = model_cls(**args)

                func(analyzer, data, args)
            except ValidationError as exception:
                analyzer._log_event(
                    category=EventCategory.RUNTIME,
                    description="Validation error during analysis",
                    data=get_exception_traceback(exception),
                    priority=EventPriority.CRITICAL,
                    console_log=True,
                )
                analyzer.result.status = ExecutionStatus.EXECUTION_FAILURE
            except Exception as exception:
                analyzer._log_event(
                    category=EventCategory.RUNTIME,
                    description=f"Exception during data analysis: {str(exception)}",
                    data=get_exception_traceback(exception),
                    priority=EventPriority.CRITICAL,
                    console_log=True,
                )
                analyzer.result.status = ExecutionStatus.EXECUTION_FAILURE

        result = analyzer.result
        result.finalize(analyzer.logger)

        analyzer._run_hooks(result)

        return result

    return wrapper


class DataAnalyzer(Task, abc.ABC, Generic[TDataModel, TAnalyzeArg]):
    """Parent class for all data analyzers"""

    TASK_TYPE = "DATA_ANALYZER"

    DATA_MODEL: Type[TDataModel]

    def __init_subclass__(cls, **kwargs) -> None:
        super().__init_subclass__(**kwargs)
        if not inspect.isabstract(cls) and cls.DATA_MODEL is None:
            raise TypeError(f"No data model set for {cls.__name__}")

        if hasattr(cls, "analyze_data"):
            cls.analyze_data = analyze_decorator(cls.analyze_data)

    @abc.abstractmethod
    def analyze_data(
        self,
        data: TDataModel,
        args: Optional[TAnalyzeArg | dict],
    ) -> TaskResult:
        """Analyze data"""
