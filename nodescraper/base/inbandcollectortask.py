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

from nodescraper.connection.inband import InBandConnection
from nodescraper.connection.inband.inband import CommandArtifact, FileArtifact
from nodescraper.enums import EventPriority, OSFamily, SystemInteractionLevel
from nodescraper.generictypes import TCollectArg, TDataModel
from nodescraper.interfaces import DataCollector, TaskResultHook
from nodescraper.interfaces.task import SystemCompatibilityError
from nodescraper.models import SystemInfo


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
    ) -> CommandArtifact:
        """
        Run a command on the SUT and return the result.

        Args:
            command (str): command to run on the SUT.
            sudo (bool, optional): whether to run the command with sudo. Defaults to False.
            timeout (int, optional): command timeout in seconds. Defaults to 300.
            strip (bool, optional): whether output should be stripped. Defaults to True.
            log_artifact (bool, optional): whether we should log the command result. Defaults to True.

        Returns:
            CommandArtifact: The result of the command execution, which includes stdout, stderr, and exit code.
        """
        command_res = self.connection.run_command(
            command=command, sudo=sudo, timeout=timeout, strip=strip
        )
        if log_artifact:
            self.result.artifacts.append(command_res)

        return command_res

    def _read_sut_file(
        self, filename: str, encoding="utf-8", strip: bool = True, log_artifact=True
    ) -> FileArtifact:
        """
        Read a file from the SUT and return its content.

        Args:
            filename (str): path to the file on the SUT.
            encoding (str, optional): encoding to use when reading the file. Defaults to "utf-8".
            strip (bool, optional): whether the file contents should be stripped. Defaults to True.
            log_artifact (bool, optional): whether we should log the contents of the file. Defaults to True.

        Returns:
            FileArtifact: The content of the file read from the SUT, which includes the file name and content
        """
        file_res = self.connection.read_file(filename=filename, encoding=encoding, strip=strip)
        if log_artifact:
            self.result.artifacts.append(file_res)
        return file_res
