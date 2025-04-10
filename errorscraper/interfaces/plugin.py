import abc
import inspect
import logging
from typing import Callable, Generic, Optional, Type

from errorscraper.constants import DEFAULT_LOGGER
from errorscraper.hooks.filesystemloghook import FileSystemLogHook
from errorscraper.models import PluginResult, SystemInfo

from .connectionmanager import TConnectArg, TConnectionManager
from .taskhook import TaskHook


class PluginInterface(abc.ABC, Generic[TConnectionManager, TConnectArg]):

    CONNECTION_TYPE: Optional[Type[TConnectionManager]] = None

    def __init__(
        self,
        system_info: Optional[SystemInfo] = None,
        logger: Optional[logging.Logger] = None,
        connection_manager: Optional[TConnectionManager] = None,
        connection_args: Optional[TConnectArg | dict] = None,
        task_hooks: Optional[list[TaskHook]] = None,
        log_path: Optional[str] = None,
        queue_callback: Optional[Callable] = None,
        **kwargs,
    ):
        if logger is None:
            logger = logging.getLogger(DEFAULT_LOGGER)
        self.logger = logger

        if system_info is None:
            system_info = SystemInfo()
        self.system_info = system_info

        if not task_hooks:
            task_hooks = []
        self.task_hooks = task_hooks

        if log_path:
            for hook in self.task_hooks:
                if isinstance(hook, FileSystemLogHook):
                    break
            else:
                self.task_hooks.append(FileSystemLogHook(log_base_path=log_path))
        self.log_path = log_path

        self.queue_callback = queue_callback

        self.connection_manager = connection_manager

        if connection_args and self.CONNECTION_TYPE and not self.connection_manager:
            self.connection_manager = self.CONNECTION_TYPE(
                system_info=self.system_info,
                logger=logger,
                connection_args=connection_args,
                parent=self.__class__.__name__,
                task_hooks=self.task_hooks,
            )

    @classmethod
    def is_valid(cls):
        if inspect.isabstract(cls):
            return False
        return True

    @abc.abstractmethod
    def run(self, **kwargs) -> PluginResult:
        pass
