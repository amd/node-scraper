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
import json
import logging
import os
from pathlib import Path
from typing import Annotated, Any, Generic, Optional, Type, Union

from pydantic import Field

from nodescraper.constants import DEFAULT_EVENT_REPORTER
from nodescraper.enums import EventPriority, ExecutionStatus, SystemInteractionLevel
from nodescraper.generictypes import TAnalyzeArg, TCollectArg, TDataModel
from nodescraper.interfaces.dataanalyzertask import DataAnalyzer
from nodescraper.interfaces.datacollectortask import DataCollector
from nodescraper.interfaces.plugin import PluginInterface
from nodescraper.models import (
    AnalyzerArgs,
    CollectorArgs,
    DataModel,
    DataPluginResult,
    PluginResult,
    SystemInfo,
    TaskResult,
)
from nodescraper.utils import pascal_to_snake

from .connectionmanager import TConnectArg, TConnectionManager
from .task import SystemCompatibilityError
from .taskresulthook import TaskResultHook

CollectorClasses = Union[
    Type[DataCollector],
    tuple[Type[DataCollector], ...],
    list[Type[DataCollector]],
]

CollectorArgsClasses = Union[
    Type[CollectorArgs],
    dict[str, Type[CollectorArgs]],
]


class DataPlugin(
    PluginInterface, Generic[TConnectionManager, TConnectArg, TDataModel, TCollectArg, TAnalyzeArg]
):
    """Plugin used to collect and analyze data"""

    DATA_MODEL: Type[TDataModel]

    CONNECTION_TYPE: Optional[Type[TConnectionManager]]

    COLLECTOR: Optional[CollectorClasses] = None

    COLLECTOR_ARGS: Optional[CollectorArgsClasses] = None

    ANALYZER: Optional[Type[DataAnalyzer]] = None

    ANALYZER_ARGS: Optional[Type[AnalyzerArgs]] = None

    def __init__(
        self,
        system_info: SystemInfo,
        logger: Optional[logging.Logger] = None,
        connection_manager: Optional[TConnectionManager] = None,
        connection_args: Optional[Union[TConnectArg, dict]] = None,
        task_result_hooks: Optional[list[TaskResultHook]] = None,
        log_path: Optional[str] = None,
        event_reporter: str = DEFAULT_EVENT_REPORTER,
        session_id: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(
            system_info,
            logger,
            connection_manager,
            connection_args,
            task_result_hooks,
            log_path,
            event_reporter=event_reporter,
            session_id=session_id,
            **kwargs,
        )
        self._validate_class_var()
        self.collection_result: TaskResult = TaskResult(
            status=ExecutionStatus.NOT_RAN,
            message=f"Data collection not ran for {self.__class__.__name__}",
        )
        self.analysis_result: TaskResult = TaskResult(
            status=ExecutionStatus.NOT_RAN,
            message=f"Data analysis not ran for {self.__class__.__name__}",
        )
        self._data: Optional[TDataModel] = None

    @classmethod
    def get_collector_classes(cls) -> tuple[Type[DataCollector], ...]:
        """Return all collector classes configured on this plugin."""
        collector = cls.COLLECTOR
        if collector is None:
            return ()
        if isinstance(collector, (tuple, list)):
            return tuple(collector)
        return (collector,)

    @classmethod
    def _collector_args_class(
        cls, collector_cls: Type[DataCollector]
    ) -> Optional[Type[CollectorArgs]]:
        collector_args = cls.COLLECTOR_ARGS
        if isinstance(collector_args, dict):
            return collector_args.get(collector_cls.__name__)
        return collector_args

    @classmethod
    def _validate_collector_args(cls) -> None:
        collector_args = cls.COLLECTOR_ARGS
        if collector_args is None:
            return
        if isinstance(collector_args, dict):
            for collector_name, args_cls in collector_args.items():
                if not isinstance(args_cls, type) or not issubclass(args_cls, CollectorArgs):
                    raise TypeError(
                        f"COLLECTOR_ARGS[{collector_name!r}] must be a CollectorArgs subclass, "
                        f"got {args_cls!r}"
                    )
            return
        if not isinstance(collector_args, type) or not issubclass(collector_args, CollectorArgs):
            raise TypeError(
                f"COLLECTOR_ARGS must be a CollectorArgs subclass or dict, got {collector_args!r}"
            )

    @classmethod
    def _validate_class_var(cls):
        if not hasattr(cls, "DATA_MODEL"):
            raise TypeError(f"No data model set for {cls.__name__}")

        if cls.DATA_MODEL is None:
            raise TypeError("DATA_MODEL class variable not defined")

        if not cls.get_collector_classes() and not cls.ANALYZER:
            raise TypeError("No collector or analyzer task defined")

        if cls.get_collector_classes() and not cls.CONNECTION_TYPE:
            raise TypeError("CONNECTION_TYPE must be defined for collector")

        for collector_cls in cls.get_collector_classes():
            if not isinstance(collector_cls, type) or not issubclass(collector_cls, DataCollector):
                raise TypeError(
                    f"COLLECTOR entries must be DataCollector subclasses, got {collector_cls!r}"
                )

        cls._validate_collector_args()

    @classmethod
    def _merge_collected_data(
        cls,
        existing: Optional[TDataModel],
        new_data: Optional[TDataModel],
    ) -> Optional[TDataModel]:
        if new_data is None:
            return existing
        if existing is None:
            return new_data
        if not isinstance(new_data, existing.__class__):
            raise TypeError(
                f"Collector returned {new_data.__class__.__name__}, "
                f"expected {existing.__class__.__name__}"
            )
        merged = {
            **existing.model_dump(exclude_unset=True),
            **new_data.model_dump(exclude_unset=True),
        }
        return existing.__class__.model_validate(merged)

    @classmethod
    def _aggregate_collection_results(
        cls,
        plugin_name: str,
        results: list[TaskResult],
    ) -> TaskResult:
        if not results:
            return TaskResult(
                parent=plugin_name,
                status=ExecutionStatus.NOT_RAN,
                message=f"Data collection not ran for {plugin_name}",
            )
        if len(results) == 1:
            return results[0]

        aggregated = TaskResult(
            parent=plugin_name,
            status=max(result.status for result in results),
            task=",".join(result.task for result in results if result.task),
        )
        messages = [result.message for result in results if result.message]
        if messages:
            aggregated.message = "; ".join(messages)
        for result in results:
            aggregated.artifacts.extend(result.artifacts)
            aggregated.events.extend(result.events)
        aggregated.details["collector_results"] = [
            result.model_dump(exclude={"artifacts", "events"}) for result in results
        ]
        return aggregated

    def _resolve_collector_args(
        self,
        collector_cls: Type[DataCollector],
        collection_args: Optional[Union[TCollectArg, dict]],
    ) -> Optional[Union[TCollectArg, dict]]:
        if collection_args is None:
            return None

        collector_name = collector_cls.__name__
        collector_names = {cls.__name__ for cls in self.get_collector_classes()}
        raw_args: Optional[Union[TCollectArg, dict]] = collection_args

        if isinstance(collection_args, dict) and collector_names.intersection(
            collection_args.keys()
        ):
            raw_args = collection_args.get(collector_name)
            if raw_args is None:
                return None

        args_cls = self._collector_args_class(collector_cls)
        if args_cls is not None and isinstance(raw_args, dict):
            return args_cls.model_validate(raw_args)
        return raw_args

    @classmethod
    def is_valid(cls) -> bool:
        """Check that all required class variables are set

        Returns:
            bool: bool indicating validity
        """
        try:
            cls._validate_class_var()
        except TypeError:
            return False

        return super().is_valid()

    @property
    def data(self) -> Optional[TDataModel]:
        """Retrieve data model

        Returns:
            Optional[TDataModel]: data model
        """
        return self._data

    @data.setter
    def data(self, data: Optional[Union[str, dict, TDataModel]]):
        if isinstance(data, (str, dict)):
            self._data = self.DATA_MODEL.import_model(data)
        elif not isinstance(data, self.DATA_MODEL):
            raise ValueError(f"data is invalid type, expected {self.DATA_MODEL.__class__.__name__}")
        else:
            self._data = data

    def collect(
        self,
        max_event_priority_level: Optional[Union[EventPriority, str]] = EventPriority.CRITICAL,
        system_interaction_level: Optional[
            Union[SystemInteractionLevel, str]
        ] = SystemInteractionLevel.INTERACTIVE,
        preserve_connection: bool = False,
        collection_args: Optional[TCollectArg] = None,
    ) -> TaskResult:
        """Run data collector task

        Args:
            max_event_priority_level (Union[EventPriority, str], optional): priority limit for events. Defaults to EventPriority.CRITICAL.
            system_interaction_level (Union[SystemInteractionLevel, str], optional): system interaction level. Defaults to SystemInteractionLevel.INTERACTIVE.
            preserve_connection (bool, optional): whether we should close the connection after data collection. Defaults to False.
            collection_args (Optional[TCollectArg], optional): args for data collection (validated model). Defaults to None.

        Returns:
            TaskResult: task result for data collection
        """
        collector_classes = self.get_collector_classes()
        if not collector_classes:
            self.collection_result = TaskResult(
                parent=self.__class__.__name__,
                status=ExecutionStatus.NOT_RAN,
                message=f"Data collection not supported for {self.__class__.__name__}",
            )
            return self.collection_result

        primary_collector = collector_classes[0]

        try:
            if not self.connection_manager:
                if not self.CONNECTION_TYPE:
                    self.collection_result = TaskResult(
                        task=primary_collector.__name__,
                        parent=self.__class__.__name__,
                        status=ExecutionStatus.NOT_RAN,
                        message=f"No connection manager type provided for {self.__class__.__name__}",
                    )
                    return self.collection_result
                self.logger.info("No connection manager provide, initializing connection manager")
                self.connection_manager = self.CONNECTION_TYPE(
                    system_info=self.system_info,
                    logger=self.logger,
                    parent=self.__class__.__name__,
                    task_result_hooks=self.task_result_hooks,
                    event_reporter=self.event_reporter,
                    session_id=self.session_id,
                )

            if (
                not self.connection_manager.connection
                and self.connection_manager.result.status == ExecutionStatus.UNSET
            ):
                self.connection_manager.connect()

            # Proceed as long as a connection was established.
            if (
                self.connection_manager.connection is None
                or self.connection_manager.result.status >= ExecutionStatus.ERROR
            ):
                self.collection_result = TaskResult(
                    task=primary_collector.__name__,
                    parent=self.__class__.__name__,
                    status=ExecutionStatus.NOT_RAN,
                    message="Connection not available, data collection skipped",
                )
            else:
                collector_results: list[TaskResult] = []
                merged_data: Optional[TDataModel] = None

                for collector_cls in collector_classes:
                    collector_args = self._resolve_collector_args(collector_cls, collection_args)
                    collection_task = collector_cls(
                        system_info=self.system_info,
                        logger=self.logger,
                        system_interaction_level=system_interaction_level,
                        connection=self.connection_manager.connection,
                        max_event_priority_level=max_event_priority_level,
                        parent=self.__class__.__name__,
                        task_result_hooks=self.task_result_hooks,
                        log_path=self.log_path,
                        event_reporter=self.event_reporter,
                        session_id=self.session_id,
                    )
                    result, data = collection_task.collect_data(collector_args)
                    collector_results.append(result)
                    merged_data = self._merge_collected_data(merged_data, data)

                self.collection_result = self._aggregate_collection_results(
                    self.__class__.__name__,
                    collector_results,
                )
                self._data = merged_data

        except SystemCompatibilityError as e:
            self.collection_result = TaskResult(
                task=primary_collector.__name__,
                parent=self.__class__.__name__,
                status=ExecutionStatus.NOT_RAN,
                message=str(e),
            )
        except Exception as e:
            self.logger.exception(
                "Unhandled exception running collectors for plugin %s",
                self.__class__.__name__,
            )
            self.collection_result = TaskResult(
                task=primary_collector.__name__,
                parent=self.__class__.__name__,
                status=ExecutionStatus.EXECUTION_FAILURE,
                message=f"Unhandled exception running data collector: {str(e)}",
            )
        finally:
            if not preserve_connection and self.connection_manager:
                self.connection_manager.disconnect()

        return self.collection_result

    def analyze(
        self,
        max_event_priority_level: Optional[Union[EventPriority, str]] = EventPriority.CRITICAL,
        analysis_args: Optional[Union[TAnalyzeArg, dict]] = None,
        data: Optional[Union[str, dict, TDataModel]] = None,
    ) -> TaskResult:
        """Run data analyzer task

        Args:
            max_event_priority_level (Union[EventPriority, str], optional): priority limit for events. Defaults to EventPriority.CRITICAL.
            analysis_args (Optional[Union[TAnalyzeArg  , dict]], optional): args for data analysis. Defaults to None.
            data (Optional[Union[str, dict, TDataModel]], optional): data to analyze. Defaults to None.

        Returns:
            TaskResult: result of data analysis
        """

        if self.ANALYZER is None:
            self.analysis_result = TaskResult(
                status=ExecutionStatus.NOT_RAN,
                parent=self.__class__.__name__,
                message=f"Data analysis not supported for {self.__class__.__name__}",
            )
            return self.analysis_result

        if data:
            self.data = data

        if self.data is None:
            self.analysis_result = TaskResult(
                task=self.ANALYZER.__name__,
                parent=self.__class__.__name__,
                status=ExecutionStatus.NOT_RAN,
                message=f"No data available to analyze for {self.__class__.__name__}",
            )
            return self.analysis_result

        if (
            analysis_args is not None
            and isinstance(analysis_args, dict)
            and hasattr(self, "ANALYZER_ARGS")
            and self.ANALYZER_ARGS is not None
        ):
            analysis_args = self.ANALYZER_ARGS.model_validate(analysis_args)

        analyzer_task = self.ANALYZER(
            self.system_info,
            logger=self.logger,
            max_event_priority_level=max_event_priority_level,
            parent=self.__class__.__name__,
            task_result_hooks=self.task_result_hooks,
            event_reporter=self.event_reporter,
            session_id=self.session_id,
        )
        self.analysis_result = analyzer_task.analyze_data(self.data, analysis_args)
        return self.analysis_result

    def run(
        self,
        collection: Annotated[
            bool,
            "Run the collector (True) or skip it (False).",
        ] = True,
        analysis: Annotated[
            bool,
            "Run the analyzer (True) or skip it (False).",
        ] = True,
        max_event_priority_level: Union[EventPriority, str] = EventPriority.CRITICAL,
        system_interaction_level: Annotated[
            Union[SystemInteractionLevel, str],
            "System interaction level (e.g. PASSIVE, INTERACTIVE, DISRUPTIVE).",
        ] = SystemInteractionLevel.INTERACTIVE,
        preserve_connection: bool = False,
        data: Annotated[
            Optional[Union[str, dict, TDataModel]],
            Field(
                description=(
                    "Path to pre-collected data"
                    "; use with --collection False to run the analyzer only."
                ),
            ),
        ] = None,
        collection_args: Optional[Union[TCollectArg, dict]] = None,
        analysis_args: Optional[Union[TAnalyzeArg, dict]] = None,
    ) -> PluginResult:
        """Run plugin

        Args:
            collection (bool, optional): Enable data collection. Defaults to True.
            analysis (bool, optional): Enable data analysis. Defaults to True.
            max_event_priority_level (Union[EventPriority, str], optional): Max priority level to assign to events. Defaults to EventPriority.CRITICAL.
            system_interaction_level (Union[SystemInteractionLevel, str], optional): System interaction level. Defaults to SystemInteractionLevel.INTERACTIVE.
            preserve_connection (bool, optional): Whether to close the connection when data collection is complete. Defaults to False.
            data (Optional[Union[str, dict, TDataModel]], optional): Input data. Defaults to None.
            collection_args (Optional[Union[TCollectArg  , dict]], optional): Arguments for data collection. Defaults to None.
            analysis_args (Optional[Union[TAnalyzeArg  , dict]], optional): Arguments for data analysis. Defaults to None.

        Returns:
            PluginResult: Plugin result
        """
        self.logger.info("Running plugin %s", self.__class__.__name__)
        if collection:
            self.collect(
                max_event_priority_level=max_event_priority_level,
                system_interaction_level=system_interaction_level,
                collection_args=collection_args,
                preserve_connection=preserve_connection,
            )

        if analysis:
            self.analyze(
                max_event_priority_level=max_event_priority_level,
                analysis_args=analysis_args,
                data=data,
            )

        status = max(self.collection_result.status, self.analysis_result.status)

        message = ""
        if status == ExecutionStatus.NOT_RAN:
            message = "Plugin tasks not ran"
        elif status in [
            ExecutionStatus.ERROR,
            ExecutionStatus.EXECUTION_FAILURE,
            ExecutionStatus.WARNING,
        ]:
            failure_parts: list[str] = []
            for label, task_result in (
                ("Collection", self.collection_result),
                ("Analysis", self.analysis_result),
            ):
                if task_result.status == ExecutionStatus.WARNING:
                    failure_parts.append(f"{label} warning: {task_result.message}")
                elif task_result.status in (
                    ExecutionStatus.ERROR,
                    ExecutionStatus.EXECUTION_FAILURE,
                ):
                    failure_parts.append(f"{label} error: {task_result.message}")
            message = "; ".join(failure_parts)
        else:
            message = "Plugin tasks completed successfully"

        return PluginResult(
            status=max(self.collection_result.status, self.analysis_result.status),
            source=self.__class__.__name__,
            message=message,
            result_data=DataPluginResult(
                system_data=self.data,
                collection_result=self.collection_result,
                analysis_result=self.analysis_result,
            ),
        )

    @classmethod
    def find_datamodel_path_in_run(cls, run_path: str) -> Optional[str]:
        """Find this plugin's collector datamodel file under a scraper run directory.

        Args:
            run_path: Path to a scraper log run directory (e.g. scraper_logs_*).

        Returns:
            Absolute path to the datamodel file, or None if not found.
        """
        run_path = os.path.abspath(run_path)
        if not os.path.isdir(run_path):
            return None
        data_model_cls = getattr(cls, "DATA_MODEL", None)
        if not data_model_cls:
            return None
        for collector_cls in cls.get_collector_classes():
            collector_dir = os.path.join(
                run_path,
                pascal_to_snake(cls.__name__),
                pascal_to_snake(collector_cls.__name__),
            )
            if not os.path.isdir(collector_dir):
                continue
            result_path = os.path.join(collector_dir, "result.json")
            if not os.path.isfile(result_path):
                continue
            try:
                res_payload = json.loads(Path(result_path).read_text(encoding="utf-8"))
                if res_payload.get("parent") != cls.__name__:
                    continue
            except (json.JSONDecodeError, OSError):
                continue
            want_json = data_model_cls.__name__.lower() + ".json"
            for fname in os.listdir(collector_dir):
                low = fname.lower()
                if low.endswith("datamodel.json") or low == want_json:
                    return os.path.join(collector_dir, fname)
                if low.endswith(".log"):
                    return os.path.join(collector_dir, fname)
        return None

    @classmethod
    def load_datamodel_from_path(cls, dm_path: str) -> Optional[TDataModel]:
        """Load this plugin's DATA_MODEL from a file path (JSON or .log).

        Args:
            dm_path: Path to datamodel JSON or to a .log file (if DATA_MODEL
                implements import_model for that format).

        Returns:
            Instance of DATA_MODEL or None if load fails.
        """
        dm_path = os.path.abspath(dm_path)
        if not os.path.isfile(dm_path):
            return None
        data_model_cls = getattr(cls, "DATA_MODEL", None)
        if not data_model_cls:
            return None
        try:
            if dm_path.lower().endswith(".log"):
                import_model = getattr(data_model_cls, "import_model", None)
                if not callable(import_model):
                    return None
                base_import = getattr(DataModel.import_model, "__func__", DataModel.import_model)
                if getattr(import_model, "__func__", import_model) is base_import:
                    return None
                return import_model(dm_path)
            with open(dm_path, encoding="utf-8") as f:
                data = json.load(f)
            return data_model_cls.model_validate(data)
        except (json.JSONDecodeError, OSError, Exception):
            return None

    @classmethod
    def get_extracted_errors(cls, data_model: DataModel) -> Optional[list[str]]:
        """Compute extracted errors from datamodel for compare-runs (in memory only).

        Args:
            data_model: Loaded DATA_MODEL instance.

        Returns:
            Sorted list of error match strings, or None if not applicable.
        """
        get_content = getattr(data_model, "get_compare_content", None)
        if not callable(get_content):
            return None
        try:
            content = get_content()
        except Exception:
            return None
        if not isinstance(content, str):
            return None
        analyzer_cls = getattr(cls, "ANALYZER", None)
        if not analyzer_cls:
            return None
        get_matches = getattr(analyzer_cls, "get_error_matches", None)
        if not callable(get_matches):
            return None
        try:
            matches = get_matches(content)
            return sorted(matches) if matches is not None else None
        except Exception:
            return None

    @classmethod
    def load_run_data(cls, run_path: str) -> Optional[dict[str, Any]]:
        """Load this plugin's run data from a scraper run directory for comparison.

        Args:
            run_path: Path to a scraper log run directory or to a datamodel file.

        Returns:
            Dict suitable for diffing with another run, or None if not found.
        """
        run_path = os.path.abspath(run_path)
        if not os.path.exists(run_path):
            return None
        dm_path = run_path if os.path.isfile(run_path) else cls.find_datamodel_path_in_run(run_path)
        if not dm_path:
            return None
        data_model = cls.load_datamodel_from_path(dm_path)
        if data_model is None:
            return None
        out = data_model.model_dump(mode="json")
        extracted = cls.get_extracted_errors(data_model)
        if extracted is not None:
            out["extracted_errors"] = extracted
        return out
