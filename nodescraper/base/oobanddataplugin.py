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
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Generic, Optional, Union

from nodescraper.connection.redfish import (
    RedfishConnectionManager,
    RedfishConnectionParams,
)
from nodescraper.enums import EventPriority, ExecutionStatus, SystemInteractionLevel
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

    When ``connection_args.targets`` is non-empty, runs all configured collectors
    concurrently across targets (one thread per target), keying results by
    ``target_key``. Single-target behaviour and all IB plugins are unaffected.
    """

    CONNECTION_TYPE = RedfishConnectionManager

    def _collect_for_target(
        self,
        target_key: str,
        conn: Any,
        collector_classes: tuple,
        collection_args: Any,
        system_interaction_level: Any,
        max_event_priority_level: Any,
    ) -> tuple[str, list[TaskResult], Any]:
        """Run all configured collectors for one target. Executed in a worker thread."""
        self.logger.info("Starting collection for target %r", target_key)
        target_data = None
        results: list[TaskResult] = []
        parent = f"{self.__class__.__name__}[{target_key}]"
        for collector_cls in collector_classes:
            resolved_args = self._resolve_collector_args(collector_cls, collection_args)
            task = collector_cls(
                system_info=self.system_info.model_copy(),
                connection=conn,
                logger=self.logger,
                system_interaction_level=system_interaction_level,
                max_event_priority_level=max_event_priority_level,
                parent=parent,
                task_result_hooks=self.task_result_hooks,
                event_reporter=self.event_reporter,
                session_id=self.session_id,
                log_path=self.log_path,
            )
            result, data = task.collect_data(resolved_args)
            results.append(result)
            target_data = self._merge_collected_data(target_data, data)
        self.logger.info("Finished collection for target %r", target_key)
        return target_key, results, target_data

    def analyze(
        self,
        max_event_priority_level: Optional[Union[EventPriority, str]] = EventPriority.CRITICAL,
        analysis_args: Optional[Union[TAnalyzeArg, dict]] = None,
        data: Optional[Any] = None,
    ) -> TaskResult:
        """Analyze collected data. Single-target delegates to DataPlugin.analyze().
        Multi-target runs the analyzer once per target and aggregates results."""
        multi_target_data: dict = getattr(self, "multi_target_data", None) or {}

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

    def collect(
        self,
        max_event_priority_level: Optional[Union[EventPriority, str]] = EventPriority.CRITICAL,
        system_interaction_level: Optional[
            Union[SystemInteractionLevel, str]
        ] = SystemInteractionLevel.INTERACTIVE,
        preserve_connection: bool = False,
        collection_args: Optional[TCollectArg] = None,
    ) -> TaskResult:
        """Run collectors. Single-target delegates to DataPlugin.collect().
        Multi-target runs all targets concurrently and merges results per target_key."""
        collector_classes = self.get_collector_classes()

        # Ensure the connection manager exists so we can inspect its params before connecting.
        if not self.connection_manager:
            if self.CONNECTION_TYPE is None:
                self.collection_result = TaskResult(
                    parent=self.__class__.__name__,
                    status=ExecutionStatus.NOT_RAN,
                    message=f"No connection type configured for {self.__class__.__name__}",
                )
                return self.collection_result
            self.connection_manager = self.CONNECTION_TYPE(
                system_info=self.system_info.model_copy(),
                logger=self.logger,
                parent=self.__class__.__name__,
                task_result_hooks=self.task_result_hooks,
                event_reporter=self.event_reporter,
                session_id=self.session_id,
            )

        cm = self.connection_manager
        params = cm.connection_args

        # Single-target: delegate the full lifecycle to the parent.
        if not (isinstance(params, RedfishConnectionParams) and params.is_multi_target):
            return super().collect(
                max_event_priority_level=max_event_priority_level,
                system_interaction_level=system_interaction_level,
                preserve_connection=preserve_connection,
                collection_args=collection_args,
            )

        # Multi-target path.
        if not collector_classes:
            self.collection_result = TaskResult(
                parent=self.__class__.__name__,
                status=ExecutionStatus.NOT_RAN,
                message=f"Data collection not supported for {self.__class__.__name__}",
            )
            return self.collection_result

        try:
            if cm.result.status == ExecutionStatus.UNSET:
                cm.connect()

            target_connections: dict = getattr(cm, "target_connections", None) or {}

            if not target_connections:
                self.collection_result = TaskResult(
                    parent=self.__class__.__name__,
                    status=ExecutionStatus.EXECUTION_FAILURE,
                    message="No Redfish target connections were established",
                )
                return self.collection_result

            max_w = params.max_workers or min(len(target_connections), 32)
            all_results: list[TaskResult] = []
            merged_data: dict[str, Any] = {}

            with ThreadPoolExecutor(max_workers=max_w) as executor:
                futures = {
                    executor.submit(
                        self._collect_for_target,
                        target_key,
                        conn,
                        collector_classes,
                        collection_args,
                        system_interaction_level,
                        max_event_priority_level,
                    ): target_key
                    for target_key, conn in target_connections.items()
                }
                for future in as_completed(futures):
                    target_key = futures[future]
                    try:
                        key, results, data = future.result()
                        all_results.extend(results)
                        if data is not None:
                            merged_data[key] = data
                    except Exception as exc:
                        self.logger.error("Collection failed for target %r: %s", target_key, exc)

            self.collection_result = self._aggregate_collection_results(
                self.__class__.__name__, all_results
            )
            # Multi-target results are keyed by target — not a single DataModel.
            # Store them separately so analysis gracefully returns NOT_RAN (rather
            # than crashing when it receives a dict instead of a DataModel).
            self.multi_target_data: dict[str, Any] = merged_data
            self._data = None

        except Exception as e:
            self.logger.exception(
                "Unhandled exception in multi-target collection for %s",
                self.__class__.__name__,
            )
            self.collection_result = TaskResult(
                parent=self.__class__.__name__,
                status=ExecutionStatus.EXECUTION_FAILURE,
                message=f"Unhandled exception running multi-target collection: {e}",
            )
        finally:
            if not preserve_connection:
                cm.disconnect()

        return self.collection_result
