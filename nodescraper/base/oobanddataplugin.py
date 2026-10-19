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
from pathlib import Path
from typing import Any, Generic, Optional, Union

from nodescraper.base.redfishcollectortask import _target_dir_name
from nodescraper.connection.redfish import (
    RedfishConnectionManager,
    RedfishConnectionParams,
    collected_multi_target_data,
)
from nodescraper.enums import EventPriority, ExecutionStatus, SystemInteractionLevel
from nodescraper.generictypes import TAnalyzeArg, TCollectArg, TDataModel
from nodescraper.interfaces import DataPlugin
from nodescraper.models import TaskResult
from nodescraper.taskresulthooks.filesystemloghook import hooks_for_fixed_directory
from nodescraper.utils import resolve_log_dir_name


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

    def run(  # type: ignore[override]
        self,
        collection: bool = True,
        analysis: bool = True,
        max_event_priority_level: Union[EventPriority, str] = EventPriority.CRITICAL,
        system_interaction_level: Union[
            SystemInteractionLevel, str
        ] = SystemInteractionLevel.INTERACTIVE,
        preserve_connection: bool = False,
        data: Optional[Any] = None,
        collection_args: Optional[Any] = None,
        analysis_args: Optional[Any] = None,
    ):
        """Run plugin. For multi-target OK runs, the summary includes per-target collection detail."""
        result = super().run(
            collection=collection,
            analysis=analysis,
            max_event_priority_level=max_event_priority_level,
            system_interaction_level=system_interaction_level,
            preserve_connection=preserve_connection,
            data=data,
            collection_args=collection_args,
            analysis_args=analysis_args,
        )
        cm = self.connection_manager
        if collected_multi_target_data(cm):
            # DataPlugin.run() replaces the message with "Plugin tasks completed successfully"
            # for OK status, discarding per-target detail. Restore it for multi-target runs.
            if result.status == ExecutionStatus.OK and getattr(
                self.collection_result, "message", None
            ):
                result.message = self.collection_result.message

        return result

    def analyze(
        self,
        max_event_priority_level: Optional[Union[EventPriority, str]] = EventPriority.CRITICAL,
        analysis_args: Optional[Union[TAnalyzeArg, dict]] = None,
        data: Optional[Any] = None,
    ) -> TaskResult:
        """Analyze collected data for one BMC or once per Redfish target.

        Args:
            max_event_priority_level: Priority limit for events.
            analysis_args: Analyzer arguments.
            data: Pre-collected data for a single-target run.

        Returns:
            TaskResult: Analysis result for the targets that returned data.
        """
        cm = self.connection_manager
        multi_target_data: dict = collected_multi_target_data(cm)

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

        plugin_log_dir = (
            Path(self.log_path) / resolve_log_dir_name(self.__class__.__name__)
            if self.log_path
            else None
        )
        analyzer_name = resolve_log_dir_name(self.ANALYZER.__name__)

        analysis_results: list[TaskResult] = []
        for target_key, target_data in multi_target_data.items():
            safe_key = _target_dir_name(target_key)
            target_hooks = self.task_result_hooks
            if plugin_log_dir is not None:
                target_hooks = hooks_for_fixed_directory(
                    self.task_result_hooks,
                    str(plugin_log_dir / analyzer_name / safe_key),
                )
            analyzer_task = self.ANALYZER(
                system_info=self.system_info.model_copy(),
                logger=self.logger,
                max_event_priority_level=max_event_priority_level or EventPriority.CRITICAL,
                parent=safe_key,
                task_result_hooks=target_hooks,
                event_reporter=self.event_reporter,
                session_id=self.session_id,
            )
            analysis_results.append(analyzer_task.analyze_data(target_data, analysis_args))

        self.analysis_result = self._aggregate_collection_results(
            self.__class__.__name__, analysis_results
        )
        return self.analysis_result
