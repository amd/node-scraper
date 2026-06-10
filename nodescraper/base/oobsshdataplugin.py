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
from __future__ import annotations

from logging import Logger
from typing import Generic, Optional, Union

from nodescraper.connection.inband.inbandmanager import InBandConnectionManager
from nodescraper.connection.redfish import (
    RedfishConnectionManager,
    RedfishConnectionParams,
    redfish_params_to_ssh,
)
from nodescraper.enums import EventPriority
from nodescraper.generictypes import TAnalyzeArg, TCollectArg, TDataModel
from nodescraper.interfaces import DataPlugin
from nodescraper.interfaces.taskresulthook import TaskResultHook
from nodescraper.models import SystemInfo


class _OobSshConnectionManager(InBandConnectionManager):
    """Internal SSH transport for OOB plugins; uses Redfish BMC credentials."""

    def __init__(
        self,
        system_info: SystemInfo,
        logger: Optional[Logger] = None,
        max_event_priority_level: Union[EventPriority, str] = EventPriority.CRITICAL,
        parent: Optional[str] = None,
        task_result_hooks: Optional[list[TaskResultHook]] = None,
        connection_args: Optional[Union[RedfishConnectionParams, dict]] = None,
        **kwargs,
    ):
        if connection_args is not None:
            connection_args = redfish_params_to_ssh(connection_args)
        super().__init__(
            system_info=system_info,
            logger=logger,
            max_event_priority_level=max_event_priority_level,
            parent=parent,
            task_result_hooks=task_result_hooks,
            connection_args=connection_args,
            **kwargs,
        )


class OOBSSHDataPlugin(
    DataPlugin[
        RedfishConnectionManager,
        RedfishConnectionParams,
        TDataModel,
        TCollectArg,
        TAnalyzeArg,
    ],
    Generic[TDataModel, TCollectArg, TAnalyzeArg],
):
    """Base class for out-of-band (OOB) plugins that run shell commands on the BMC.

    Configure the BMC using ``RedfishConnectionManager`` in the connection config.
    Commands are executed over SSH (port 22) using the same host/username/password.
    """

    CONNECTION_TYPE = RedfishConnectionManager
