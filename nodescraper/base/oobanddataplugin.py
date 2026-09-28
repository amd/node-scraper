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
from typing import Any, Generic, Optional, Union

from nodescraper.connection.redfish import (
    RedfishConnectionManager,
    RedfishConnectionParams,
)
from nodescraper.enums import EventPriority, ExecutionStatus
from nodescraper.generictypes import TAnalyzeArg, TCollectArg, TDataModel
from nodescraper.interfaces import DataPlugin
from nodescraper.models import TaskResult


class OOBandDataPlugin(
    DataPlugin[
        RedfishConnectionManager,
        RedfishConnectionParams,
        TDataModel,
        TCollectArg,
        TAnalyzeArg,
    ],
    Generic[TDataModel, TCollectArg, TAnalyzeArg],
):
    """Base class for OOB plugins (Redfish). Adds multi-target support.

    Multi-target collection is handled transparently by RedfishDataCollector's
    __init_subclass__ wrapper; this class only needs to override analyze() to run
    the analyzer once per target after collection completes.
    """

    CONNECTION_TYPE = RedfishConnectionManager

    def analyze(
        self,
        max_event_priority_level: Optional[Union[EventPriority, str]] = EventPriority.CRITICAL,
        analysis_args: Optional[Union[TAnalyzeArg, dict]] = None,
        data: Optional[Any] = None,
    ) -> TaskResult:
        """Analyze collected data. Single-target delegates to DataPlugin.analyze().
        Multi-target runs the analyzer once per target and aggregates results."""
        cm = self.connection_manager
        multi_target_data: dict = getattr(cm, "_multi_target_data", None) or {}

        if not multi_target_data:
            return super().analyze(
                max_event_priority_level=max_event_priority_level,
                analysis_args=analysis_args,
                data=data,
            )

        if self.ANALYZER is None:
            self.analysis_result = TaskResult(
                status=ExecutionStatus.NOT_RAN,
                parent=self.__class__.__name__,
                message=f"Data analysis not supported for {self.__class__.__name__}",
            )
            return self.analysis_result

        if (
            analysis_args is not None
            and isinstance(analysis_args, dict)
            and hasattr(self, "ANALYZER_ARGS")
            and self.ANALYZER_ARGS is not None
        ):
            analysis_args = self.ANALYZER_ARGS.model_validate(analysis_args)  # type: ignore[assignment]

        analysis_results: list[TaskResult] = []
        for target_key, target_data in multi_target_data.items():
            parent = f"{self.__class__.__name__}[{target_key}]"
            analyzer_task = self.ANALYZER(
                system_info=self.system_info.model_copy(),
                logger=self.logger,
                max_event_priority_level=max_event_priority_level or EventPriority.CRITICAL,
                parent=parent,
                task_result_hooks=self.task_result_hooks,
                event_reporter=self.event_reporter,
                session_id=self.session_id,
            )
            analysis_results.append(analyzer_task.analyze_data(target_data, analysis_args))

        self.analysis_result = self._aggregate_collection_results(
            self.__class__.__name__, analysis_results
        )
        return self.analysis_result
