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
        log_path: Optional[str] = None,
    ):
        if logger is None:
            logger = logging.getLogger(DEFAULT_LOGGER)
        self.logger = logger
        self.log_path = log_path

    @abc.abstractmethod
    def collate_results(
        self, plugin_results: list[PluginResult], connection_results: list[TaskResult], **kwargs
    ):
        """Function to process the result of a plugin executor run

        Args:
            plugin_results (list[PluginResult]): list of plugin result objects
            connection_results (list[TaskResult]): list of task result objests from connection setup
        """
