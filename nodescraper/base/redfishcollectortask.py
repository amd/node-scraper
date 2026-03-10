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
from typing import Generic, Optional, Union

from nodescraper.connection.redfish import RedfishConnection, RedfishGetResult
from nodescraper.enums import EventPriority
from nodescraper.generictypes import TCollectArg, TDataModel
from nodescraper.interfaces import DataCollector, TaskResultHook
from nodescraper.models import SystemInfo


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
        **kwargs,
    ):
        super().__init__(
            system_info=system_info,
            connection=connection,
            logger=logger,
            max_event_priority_level=max_event_priority_level,
            parent=parent,
            task_result_hooks=task_result_hooks,
            **kwargs,
        )

    def _run_redfish_get(
        self,
        path: str,
        log_artifact: bool = True,
    ) -> RedfishGetResult:
        """Run a Redfish GET request and return the result.

        Args:
            path: Redfish URI path
            log_artifact: If True, append the result to self.result.artifacts.

        Returns:
            RedfishGetResult: path, success, data (or error), status_code.
        """
        res = self.connection.run_get(path)
        if log_artifact:
            self.result.artifacts.append(res)
        return res
