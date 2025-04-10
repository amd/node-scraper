# Copyright (C) 2024 Advanced Micro Devices, Inc. All rights reserved.
import logging
from typing import Generic, Optional

from errorscraper.connection.inband import InBandConnection
from errorscraper.enums import EventPriority, OSFamily, SystemInteractionLevel
from errorscraper.models import SystemInfo
from errorscraper.types import TCollectArg, TDataModel

from .datacollectortask import DataCollector
from .task import SystemCompatibilityError
from .taskhook import TaskHook


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
        system_interaction_level: SystemInteractionLevel = SystemInteractionLevel.STANDARD,
        max_event_priority_level: EventPriority | str = EventPriority.CRITICAL,
        parent: Optional[str] = None,
        task_hooks: Optional[list[TaskHook]] = None,
        **kwargs,
    ):
        super().__init__(
            system_info=system_info,
            system_interaction_level=system_interaction_level,
            max_event_priority_level=max_event_priority_level,
            logger=logger,
            connection=connection,
            parent=parent,
            task_hooks=task_hooks,
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
