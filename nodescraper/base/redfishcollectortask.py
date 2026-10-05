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
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import wraps
from pathlib import Path
from typing import Any, Generic, Optional, Union

from nodescraper.connection.redfish import (
    MultiTargetRedfishConnection,
    RedfishConnection,
    RedfishGetResult,
)
from nodescraper.constants import DEFAULT_EVENT_REPORTER
from nodescraper.enums import EventPriority, ExecutionStatus
from nodescraper.generictypes import TCollectArg, TDataModel
from nodescraper.interfaces import DataCollector, TaskResultHook
from nodescraper.interfaces.dataplugin import DataPlugin
from nodescraper.models import SystemInfo, TaskResult
from nodescraper.taskresulthooks.filesystemloghook import hooks_for_fixed_directory

_HARD_FAIL = {ExecutionStatus.ERROR, ExecutionStatus.EXECUTION_FAILURE}
_TARGET_SUCCESS = {ExecutionStatus.OK, ExecutionStatus.WARNING}


class _TargetPrefixAdapter(logging.LoggerAdapter):
    """Prepend ``[target_key]`` to every log message emitted by a per-target collector thread."""

    def __init__(self, logger: logging.Logger, extra: dict[str, Any]) -> None:
        super().__init__(logger, extra)
        self._target_key: str = extra["target_key"]

    def process(self, msg: str, kwargs: Any) -> tuple[str, Any]:
        return f"[{self._target_key}] {msg}", kwargs


def _target_dir_name(target_key: str) -> str:
    """Return a filesystem-safe directory name for a target key.

    Args:
        target_key: Target identifier from the connection config.

    Returns:
        str: Directory name containing only letters, numbers, dot, underscore, and dash.
    """
    # Collapse characters that are unsafe in a log directory name.
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", target_key).strip("._")
    return cleaned or "target"


def combine_target_results(parent: str, results: list[TaskResult]) -> TaskResult:
    """Merge per-target task results.

    Args:
        parent: Parent name stored on the combined result.
        results: Per-target task results.

    Returns:
        TaskResult: Combined result. Mixed success and failure stays at warning.
    """
    aggregated = DataPlugin._aggregate_collection_results(parent, results)
    hard_fail = any(result.status in _HARD_FAIL for result in results)
    succeeded = any(result.status in _TARGET_SUCCESS for result in results)

    # Display one line per target so the summary table is easy to read.
    messages = [r.message for r in results if r.message]
    if messages:
        prefix = (
            "One or more targets failed; continuing with the rest.\n"
            if (hard_fail and succeeded)
            else ""
        )
        aggregated.message = prefix + "\n".join(messages)
        if hard_fail and succeeded:
            aggregated.status = ExecutionStatus.WARNING

    return aggregated


class RedfishDataCollector(
    DataCollector[RedfishConnection, TDataModel, TCollectArg],
    Generic[TDataModel, TCollectArg],
):
    """Base class for data collectors that use a Redfish connection."""

    def __init__(
        self,
        system_info: SystemInfo,
        connection: RedfishConnection,
        logger: Optional[logging.Logger] = None,
        max_event_priority_level: Union[EventPriority, str] = EventPriority.CRITICAL,
        parent: Optional[str] = None,
        task_result_hooks: Optional[list[TaskResultHook]] = None,
        event_reporter: str = DEFAULT_EVENT_REPORTER,
        session_id: Optional[str] = None,
        **kwargs,
    ):
        """Creates a RedfishDataCollector instance.

        Args:
            system_info (SystemInfo): system info object for target system for data collection
            connection (TConnection): connection object for the data collector
            logger (Optional[logging.Logger], optional): python logger object. Defaults to None.
            max_event_priority_level (Union[EventPriority, str], optional): priority limit for events. Defaults to EventPriority.CRITICAL.
            parent (Optional[str], optional): parent task identifier. Defaults to None.
            task_result_hooks (Optional[list[TaskResultHook]], optional): list of task result hooks. Defaults to None.
            event_reporter (str, optional): Reporter string stored on emitted events. Defaults to DEFAULT_EVENT_REPORTER.
            session_id (Optional[str], optional): session identifier. Defaults to None.
        """
        super().__init__(
            system_info=system_info,
            connection=connection,
            logger=logger,
            max_event_priority_level=max_event_priority_level,
            parent=parent,
            task_result_hooks=task_result_hooks,
            event_reporter=event_reporter,
            session_id=session_id,
            **kwargs,
        )

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Wrap each concrete collector's collect_data with multi-target detection.

        Execution order when collect_data is called:
        1. _multi_target_wrapper (outermost) — checks for MultiTargetRedfishConnection
        2. collect_decorator (from DataCollector) — handles hooks, finalization
        3. Concrete collect_data implementation (innermost)

        In multi-target mode a fresh collector instance is created per target so that
        concurrent threads never share mutable state.
        """
        super().__init_subclass__(**kwargs)  # applies collect_decorator via DataCollector
        if "collect_data" not in vars(cls):
            return
        inner = cls.collect_data  # already wrapped by collect_decorator at this point

        @wraps(inner)
        def _multi_target_wrapper(
            collector: "RedfishDataCollector",
            args: Any = None,
            *,
            _fn: Any = inner,
        ) -> tuple[TaskResult, Any]:
            if not isinstance(collector.connection, MultiTargetRedfishConnection):
                return _fn(collector, args)

            multi_conn: MultiTargetRedfishConnection = collector.connection  # type: ignore[assignment]
            parent_name = collector.parent or type(collector).__name__
            all_results: list[TaskResult] = [
                TaskResult(
                    status=ExecutionStatus.WARNING,
                    parent=f"{parent_name}[{target_key}]",
                    message=message,
                )
                for target_key, message in multi_conn.failed_targets.items()
            ]
            target_count = len(multi_conn.target_connections)
            configured_workers = multi_conn.max_workers or target_count
            max_workers = min(configured_workers, target_count, 32) if target_count else 1

            def _run_for_target(
                target_key: str, conn: RedfishConnection
            ) -> tuple[str, TaskResult, Any]:
                safe_key = _target_dir_name(target_key)
                collector_log = getattr(collector, "log_path", None)
                target_log = str(Path(collector_log) / safe_key) if collector_log else None
                per_target_hooks = (
                    hooks_for_fixed_directory(collector.task_result_hooks, target_log)
                    if target_log
                    else list(collector.task_result_hooks)
                )

                target_collector = type(collector)(
                    system_info=collector.system_info.model_copy(),
                    connection=conn,
                    logger=_TargetPrefixAdapter(collector.logger, {"target_key": target_key}),  # type: ignore[arg-type]
                    max_event_priority_level=getattr(
                        collector, "max_event_priority_level", EventPriority.CRITICAL
                    ),
                    parent=safe_key,
                    task_result_hooks=per_target_hooks,
                    event_reporter=collector.event_reporter,
                    session_id=collector.session_id,
                    log_path=target_log,
                    system_interaction_level=getattr(collector, "system_interaction_level", None),
                )
                collector.logger.info(
                    "Starting collection for target %r using %s", target_key, parent_name
                )
                result, data = _fn(target_collector, args)
                collector.logger.info("Finished collection for target %r", target_key)

                # Prefix result message with target key for attribution in the summary table.
                if result.message:
                    result.message = f"[{target_key}] {result.message}"

                return target_key, result, data

            if multi_conn.target_connections:
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    futures = {
                        executor.submit(_run_for_target, tk, conn): tk
                        for tk, conn in multi_conn.target_connections.items()
                    }
                    for future in as_completed(futures):
                        target_key = futures[future]
                        try:
                            tk, result, data = future.result()
                            all_results.append(result)
                            if data is not None:
                                multi_conn.multi_target_data[tk] = data
                        except Exception as exc:
                            collector.logger.error(
                                "Collection failed for target %r: %s", target_key, exc
                            )
                            all_results.append(
                                TaskResult(
                                    status=ExecutionStatus.EXECUTION_FAILURE,
                                    parent=f"{parent_name}[{target_key}]",
                                    message=f"Collection failed for target {target_key!r}: {exc}",
                                )
                            )

            if not all_results:
                return (
                    TaskResult(
                        status=ExecutionStatus.NOT_RAN,
                        parent=parent_name,
                        message="No Redfish targets were collected",
                    ),
                    None,
                )
            return combine_target_results(parent_name, all_results), None

        cls.collect_data = _multi_target_wrapper  # type: ignore[method-assign, assignment]

    def _run_redfish_get(
        self,
        path: str,
        log_artifact: bool = True,
        html_view: Optional[bool] = None,
    ) -> RedfishGetResult:
        """Run a Redfish GET request and return the result.

        Args:
            path: Redfish URI path
            log_artifact: If True, append the result to self.result.artifacts.
            html_view: When set, controls HTML artifact output. When omitted, uses
                collection_args.html_view.

        Returns:
            RedfishGetResult: path, success, data (or error), status_code.
        """
        res = self.connection.run_get(path)
        effective_html_view = self._effective_html_view(html_view)
        if log_artifact or effective_html_view:
            res.log_html = effective_html_view
            self.result.artifacts.append(res)
        return res

    def _run_redfish_get_paged(
        self,
        path: str,
        max_pages: int = 200,
        log_artifact: bool = True,
        html_view: Optional[bool] = None,
    ) -> RedfishGetResult:
        """
        Run a Redfish GET and follow Members@odata.nextLink pagination, merging all pages into a single response.

        Args:
            path (str): Redfish URI path.
            max_pages (int, optional): safety cap on the number of pages to follow. Defaults to 200.
            log_artifact (bool, optional): whether we should log the merged result. Defaults to True.
            html_view (Optional[bool], optional): whether to include this request in HTML artifacts.
                When omitted, uses collection_args.html_view.

        Returns:
            RedfishGetResult: path, success, merged data (or error), status_code.
        """
        res = self.connection.run_get_paged(path, max_pages=max_pages)
        effective_html_view = self._effective_html_view(html_view)
        if log_artifact or effective_html_view:
            res.log_html = effective_html_view
            self.result.artifacts.append(res)
        return res

    def _append_redfish_artifact(
        self,
        res: RedfishGetResult,
        *,
        log_artifact: bool = True,
        html_view: Optional[bool] = None,
    ) -> RedfishGetResult:
        """Append a Redfish GET result to task artifacts with log flags applied."""
        effective_html_view = self._effective_html_view(html_view)
        if log_artifact or effective_html_view:
            res.log_html = effective_html_view
            self.result.artifacts.append(res)
        return res
