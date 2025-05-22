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
import logging
from typing import Generic, Optional, Type

from errorscraper.enums import EventPriority, ExecutionStatus, SystemInteractionLevel
from errorscraper.generictypes import TAnalyzeArg, TCollectArg, TDataModel
from errorscraper.interfaces.dataanalyzertask import DataAnalyzer
from errorscraper.interfaces.datacollectortask import DataCollector
from errorscraper.interfaces.plugin import PluginInterface
from errorscraper.models import DataPluginResult, PluginResult, SystemInfo, TaskResult

from .connectionmanager import TConnectArg, TConnectionManager
from .task import SystemCompatibilityError
from .taskresulthook import TaskResultHook


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
        task_result_hooks: Optional[list[TaskResultHook]] = None,
        log_path: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(
            system_info,
            logger,
            connection_manager,
            connection_args,
            task_result_hooks,
            log_path,
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
    def data(self) -> TDataModel | None:
        """Retrieve data model

        Returns:
            TDataModel | None: data model
        """
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
        system_interaction_level: SystemInteractionLevel | str = SystemInteractionLevel.INTERACTIVE,
        preserve_connection: bool = False,
        collection_args: Optional[TCollectArg | dict] = None,
    ) -> TaskResult:
        """Run data collector task

        Args:
            max_event_priority_level (EventPriority | str, optional): priority limit for events. Defaults to EventPriority.CRITICAL.
            system_interaction_level (SystemInteractionLevel | str, optional): system interaction level. Defaults to SystemInteractionLevel.INTERACTIVE.
            preserve_connection (bool, optional): whether we should close the connection after data collection. Defaults to False.
            collection_args (Optional[TCollectArg  |  dict], optional): args for data collection. Defaults to None.

        Returns:
            TaskResult: task result for data collection
        """
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
                    task_result_hooks=self.task_result_hooks,
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
                    task_result_hooks=self.task_result_hooks,
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
        """Run data analyzer task

        Args:
            max_event_priority_level (EventPriority | str, optional): priority limit for events. Defaults to EventPriority.CRITICAL.
            analysis_args (Optional[TAnalyzeArg  |  dict], optional): args for data analysis. Defaults to None.
            data (Optional[str  |  dict  |  TDataModel], optional): data to analyze. Defaults to None.

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
            task_result_hooks=self.task_result_hooks,
        )
        self.analysis_result = analyzer_task.analyze_data(self.data, analysis_args)
        return self.analysis_result

    def run(
        self,
        collection: bool = True,
        analysis: bool = True,
        max_event_priority_level: EventPriority | str = EventPriority.CRITICAL,
        system_interaction_level: SystemInteractionLevel | str = SystemInteractionLevel.INTERACTIVE,
        preserve_connection: bool = False,
        data: Optional[str | dict | TDataModel] = None,
        collection_args: Optional[TCollectArg | dict] = None,
        analysis_args: Optional[TAnalyzeArg | dict] = None,
    ) -> PluginResult:
        """Run plugin

        Args:
            collection (bool, optional): Enable data collection. Defaults to True.
            analysis (bool, optional): Enable data analysis. Defaults to True.
            max_event_priority_level (EventPriority | str, optional): Max priority level to assign to events. Defaults to EventPriority.CRITICAL.
            system_interaction_level (SystemInteractionLevel | str, optional): System interaction level. Defaults to SystemInteractionLevel.INTERACTIVE.
            preserve_connection (bool, optional): Whether to close the connection when data collection is complete. Defaults to False.
            data (Optional[str  |  dict  |  TDataModel], optional): Input data. Defaults to None.
            collection_args (Optional[TCollectArg  |  dict], optional): Arguments for data collection. Defaults to None.
            analysis_args (Optional[TAnalyzeArg  |  dict], optional): Arguments for data analysis. Defaults to None.

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
            if self.analysis_result.status > self.collection_result.status:
                if self.analysis_result.status == ExecutionStatus.WARNING:
                    message = f"Analysis warning: {self.analysis_result.message}"
                else:
                    message = f"Analysis error: {self.analysis_result.message}"
            else:
                if self.collection_result.status == ExecutionStatus.WARNING:
                    message = f"Collection warning: {self.collection_result.message}"
                else:
                    message = f"Collection error: {self.collection_result.message}"
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
