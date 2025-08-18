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
import inspect
from functools import wraps
from typing import Any, Callable, Generic, Optional, Type

from pydantic import BaseModel, ValidationError

from nodescraper.enums import EventCategory, EventPriority, ExecutionStatus
from nodescraper.generictypes import TAnalyzeArg, TDataModel
from nodescraper.interfaces.task import Task
from nodescraper.models import TaskResult
from nodescraper.models.datamodel import DataModel
from nodescraper.typeutils import TypeUtils
from nodescraper.utils import get_exception_traceback


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
                    arg_types = TypeUtils.get_func_arg_types(func)
                    analyze_arg_model = next(
                        (
                            type_class.type_class
                            for type_class in arg_types["args"].type_classes
                            if issubclass(type_class.type_class, BaseModel)
                        ),
                        None,
                    )
                    if not analyze_arg_model:
                        raise ValueError("No model defined for analysis args")
                    args = analyze_arg_model(**args)  # type: ignore
                func(analyzer, data, args)
            except ValidationError as exception:
                analyzer._log_event(
                    category=EventCategory.RUNTIME,
                    description="Validation error during analysis",
                    data={"errors": exception.errors(include_url=False)},
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

    def __init_subclass__(cls, **kwargs: dict[str, Any]) -> None:
        super().__init_subclass__(**kwargs)
        if not inspect.isabstract(cls) and cls.DATA_MODEL is None:
            raise TypeError(f"No data model set for {cls.__name__}")

        if hasattr(cls, "analyze_data"):
            setattr(cls, "analyze_data", analyze_decorator(cls.analyze_data))  # noqa

    @abc.abstractmethod
    def analyze_data(
        self,
        data: TDataModel,
        args: Optional[TAnalyzeArg],
    ) -> TaskResult:
        """Analyze the provided data and return a TaskResult

        Args:
            data (TDataModel): data to analyze
            args (Optional[TAnalyzeArg]): Optional arguments for analysis. Dicts will be handled in the decorator"

        Returns:
            TaskResult: Task result containing the analysis outcome
        """
