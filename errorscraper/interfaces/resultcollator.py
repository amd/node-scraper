import abc
import logging
from typing import Optional

from errorscraper.constants import DEFAULT_LOGGER
from errorscraper.models import PluginResult, TaskResult


class PluginResultCollator(abc.ABC):
    """Base interface for plugin result collators"""

    def __init__(
        self,
        logger: Optional[logging.Logger] = None,
        **kwargs,
    ):
        if logger is None:
            logger = logging.getLogger(DEFAULT_LOGGER)
        self.logger = logger

    @abc.abstractmethod
    def collate_results(
        self, plugin_results: list[PluginResult], connection_results: list[TaskResult], **kwargs
    ):
        """Function to process the result of a plugin executor run

        Args:
            plugin_results (list[PluginResult]): list of plugin result objects
            connection_results (list[TaskResult]): list of task result objests from connection setup
        """
