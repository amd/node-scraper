import abc
import inspect
import logging
from typing import Callable, Generic, Optional, Type

from errorscraper.constants import DEFAULT_LOGGER
from errorscraper.models import PluginResult, SystemInfo
from errorscraper.taskresulthooks.filesystemloghook import FileSystemLogHook

from .connectionmanager import TConnectArg, TConnectionManager
from .taskresulthook import TaskResultHook


class PluginInterface(abc.ABC, Generic[TConnectionManager, TConnectArg]):
    """Base plugin interface"""

    CONNECTION_TYPE: Optional[Type[TConnectionManager]] = None

    def __init__(
        self,
        system_info: Optional[SystemInfo] = None,
        logger: Optional[logging.Logger] = None,
        connection_manager: Optional[TConnectionManager] = None,
        connection_args: Optional[TConnectArg | dict] = None,
        task_result_hooks: Optional[list[TaskResultHook]] = None,
        log_path: Optional[str] = None,
        queue_callback: Optional[Callable] = None,
        **kwargs,
    ):
        """Initialize plugin

        Args:
            system_info (Optional[SystemInfo], optional): system info object. Defaults to None.
            logger (Optional[logging.Logger], optional): python logger instance. Defaults to None.
            connection_manager (Optional[TConnectionManager], optional): connection manager instance. Defaults to None.
            connection_args (Optional[TConnectArg  |  dict], optional): connection args. Defaults to None.
            task_result_hooks (Optional[list[TaskResultHook]], optional): list of task result hooks. Defaults to None.
            log_path (Optional[str], optional): path for file system logs. Defaults to None.
            queue_callback (Optional[Callable], optional): function to add additional plugins to plugin executor queue. Defaults to None.
        """
        if logger is None:
            logger = logging.getLogger(DEFAULT_LOGGER)
        self.logger = logger

        if system_info is None:
            system_info = SystemInfo()
        self.system_info = system_info

        if not task_result_hooks:
            task_result_hooks = []
        self.task_result_hooks = task_result_hooks

        if log_path:
            for hook in self.task_result_hooks:
                if isinstance(hook, FileSystemLogHook):
                    break
            else:
                self.task_result_hooks.append(FileSystemLogHook(log_base_path=log_path))

        self.log_path = log_path

        self.queue_callback = queue_callback

        self.connection_manager = connection_manager

        if connection_args and self.CONNECTION_TYPE and not self.connection_manager:
            self.connection_manager = self.CONNECTION_TYPE(
                system_info=self.system_info,
                logger=logger,
                connection_args=connection_args,
                parent=self.__class__.__name__,
                task_result_hooks=self.task_result_hooks,
            )

    @classmethod
    def is_valid(cls) -> bool:
        """Check if plugin class is valid and can be instantiated

        Returns:
            bool: class validity
        """
        if inspect.isabstract(cls):
            return False
        return True

    @abc.abstractmethod
    def run(self, **kwargs) -> PluginResult:
        """Plugin run function

        Returns:
            PluginResult: plugin result object
        """
        pass
