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
from typing import Generic, Optional

from errorscraper.connection.inband import InBandConnection
from errorscraper.enums import EventPriority, OSFamily, SystemInteractionLevel
from errorscraper.generictypes import TCollectArg, TDataModel
from errorscraper.interfaces import DataCollector, TaskResultHook
from errorscraper.interfaces.task import SystemCompatibilityError
from errorscraper.models import SystemInfo


class InBandDataCollector(
    DataCollector[InBandConnection, TDataModel, TCollectArg],
    Generic[TDataModel, TCollectArg],
):
    """Parent class for all data collectors that collect in band data"""

    SUPPORTED_OS_FAMILY: set[OSFamily] = {OSFamily.WINDOWS, OSFamily.LINUX}

    def __init__(
        self,
        system_info: SystemInfo,
        connection: InBandConnection,
        logger: Optional[logging.Logger] = None,
        system_interaction_level: SystemInteractionLevel = SystemInteractionLevel.INTERACTIVE,
        max_event_priority_level: EventPriority | str = EventPriority.CRITICAL,
        parent: Optional[str] = None,
        task_result_hooks: Optional[list[TaskResultHook]] = None,
        **kwargs,
    ):
        super().__init__(
            system_info=system_info,
            system_interaction_level=system_interaction_level,
            max_event_priority_level=max_event_priority_level,
            logger=logger,
            connection=connection,
            parent=parent,
            task_result_hooks=task_result_hooks,
        )
        if self.system_info.os_family not in self.SUPPORTED_OS_FAMILY:
            raise SystemCompatibilityError(
                f"{self.system_info.os_family.name} OS family is not supported"
            )

    def _run_sut_cmd(
        self,
        command: str,
        sudo: bool = False,
        timeout: int = 300,
        strip: bool = True,
        log_artifact: bool = True,
    ):
        command_res = self.connection.run_command(
            command=command, sudo=sudo, timeout=timeout, strip=strip
        )
        if log_artifact:
            self.result.artifacts.append(command_res)

        return command_res

    def _read_sut_file(
        self, filename: str, encoding="utf-8", strip: bool = True, log_artifact=True
    ):
        file_res = self.connection.read_file(filename=filename, encoding=encoding, strip=strip)
        if log_artifact:
            self.result.artifacts.append(file_res)
        return file_res
