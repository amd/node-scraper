import logging
from typing import Generic, Optional, Type

from errorscraper.enums import EventPriority, ExecutionStatus, SystemInteractionLevel
from errorscraper.interfaces.dataanalyzertask import DataAnalyzer
from errorscraper.interfaces.datacollectortask import DataCollector
from errorscraper.interfaces.plugin import PluginInterface
from errorscraper.models import DataPluginResult, PluginResult, SystemInfo, TaskResult
from errorscraper.types import TAnalyzeArg, TCollectArg, TDataModel

from .connectionmanager import TConnectArg, TConnectionManager
from .task import SystemCompatibilityError
from .taskhook import TaskHook


class DataPlugin(
    PluginInterface, Generic[TConnectionManager, TConnectArg, TDataModel, TCollectArg, TAnalyzeArg]
):
    """Plugin used to collect and analyze data"""

    DATA_MODEL: Type[TDataModel]

    CONNECTION_TYPE: Optional[Type[TConnectionManager]]

    COLLECTOR: Optional[Type[DataCollector]] = None

    ANALYZER: Optional[Type[DataAnalyzer]] = None

    def __init__(
        self,
        system_info: SystemInfo,
        logger: Optional[logging.Logger] = None,
        connection_manager: Optional[TConnectionManager] = None,
        connection_args: Optional[TConnectArg | dict] = None,
        task_hooks: Optional[list[TaskHook]] = None,
        log_path: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(
            system_info, logger, connection_manager, connection_args, task_hooks, log_path, **kwargs
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
        self._data: TDataModel | None = None

    @classmethod
    def _validate_class_var(cls):
        if not hasattr(cls, "DATA_MODEL"):
            raise TypeError(f"No data model set for {cls.__name__}")

        if cls.DATA_MODEL is None:
            raise TypeError("DATA_MODEL class variable not defined")

        if not cls.COLLECTOR and not cls.ANALYZER:
            raise TypeError("No collector or analyzer task defined")

        if cls.COLLECTOR and not cls.CONNECTION_TYPE:
            raise TypeError("CONNECTION_TYPE must be defined for collector")

    @classmethod
    def is_valid(cls):
        try:
            cls._validate_class_var()
        except TypeError:
            return False

        return super().is_valid()

    @property
    def data(self) -> TDataModel | None:
        return self._data

    @data.setter
    def data(self, data: str | dict | TDataModel):
        if isinstance(data, (str, dict)):
            self._data = self.DATA_MODEL.import_model(data)
        elif not isinstance(data, self.DATA_MODEL):
            raise ValueError(f"data is invalid type, expected {self.DATA_MODEL.__class__.__name__}")
        else:
            self._data = data

    def collect(
        self,
        max_event_priority_level: EventPriority | str = EventPriority.CRITICAL,
        system_interaction_level: SystemInteractionLevel | str = SystemInteractionLevel.STANDARD,
        preserve_connection: bool = False,
        collection_args: Optional[TCollectArg | dict] = None,
    ) -> TaskResult:
        if not self.COLLECTOR:
            self.collection_result = TaskResult(
                parent=self.__class__.__name__,
                status=ExecutionStatus.NOT_RAN,
                message=f"Data collection not supported for {self.__class__.__name__}",
            )
            return self.collection_result

        try:
            if not self.connection_manager:
                if not self.CONNECTION_TYPE:
                    self.collection_result = TaskResult(
                        task=self.COLLECTOR.__name__,
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
                    task_hooks=self.task_hooks,
                )

            if (
                not self.connection_manager.connection
                and self.connection_manager.result.status == ExecutionStatus.UNSET
            ):
                self.connection_manager.connect()

            if self.connection_manager.result.status != ExecutionStatus.OK:
                self.collection_result = TaskResult(
                    task=self.COLLECTOR.__name__,
                    parent=self.__class__.__name__,
                    status=ExecutionStatus.NOT_RAN,
                    message="Connection not available, data collection skipped",
                )
            else:

                collection_task = self.COLLECTOR(
                    system_info=self.system_info,
                    logger=self.logger,
                    system_interaction_level=system_interaction_level,
                    connection=self.connection_manager.connection,
                    max_event_priority_level=max_event_priority_level,
                    parent=self.__class__.__name__,
                    task_hooks=self.task_hooks,
                )
                self.collection_result, self._data = collection_task.collect_data(collection_args)

        except SystemCompatibilityError as e:
            self.collection_result = TaskResult(
                task=self.COLLECTOR.__name__,
                parent=self.__class__.__name__,
                status=ExecutionStatus.NOT_RAN,
                message=str(e),
            )
        except Exception as e:
            self.collection_result = TaskResult(
                task=self.COLLECTOR.__name__,
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
        max_event_priority_level: EventPriority | str = EventPriority.CRITICAL,
        analysis_args: Optional[TAnalyzeArg | dict] = None,
        data: Optional[str | dict | TDataModel] = None,
    ) -> TaskResult:
        if self.ANALYZER is None:
            self.analysis_result = TaskResult(
                status=ExecutionStatus.NOT_RAN,
                parent=self.__class__.__name__,
                message=f"Data analysis not supported for {self.__class__.__name__}",
            )
            return self.analysis_result

        if self.data is None:
            self.analysis_result = TaskResult(
                task=self.ANALYZER.__name__,
                parent=self.__class__.__name__,
                status=ExecutionStatus.NOT_RAN,
                message=f"No data available to analyze for {self.__class__.__name__}",
            )
            return self.analysis_result

        if data:
            self.data = data

        analyzer_task = self.ANALYZER(
            self.system_info,
            logger=self.logger,
            max_event_priority_level=max_event_priority_level,
            parent=self.__class__.__name__,
            task_hooks=self.task_hooks,
        )
        self.analysis_result = analyzer_task.analyze_data(self.data, analysis_args)
        return self.analysis_result

    def run(
        self,
        collection: bool = True,
        analysis: bool = True,
        max_event_priority_level: EventPriority | str = EventPriority.CRITICAL,
        system_interaction_level: SystemInteractionLevel | str = SystemInteractionLevel.STANDARD,
        preserve_connection: bool = False,
        data: Optional[str | dict | TDataModel] = None,
        collection_args: Optional[TCollectArg | dict] = None,
        analysis_args: Optional[TAnalyzeArg | dict] = None,
    ) -> PluginResult:
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

        return PluginResult(
            status=max(self.collection_result.status, self.analysis_result.status),
            result_data=DataPluginResult(
                system_data=self.data,
                collection_result=self.collection_result,
                analysis_result=self.analysis_result,
            ),
        )
