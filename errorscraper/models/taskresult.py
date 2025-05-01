# Copyright (C) 2024 Advanced Micro Devices, Inc. All rights reserved.
import datetime
import logging
from typing import Optional

from pydantic import BaseModel, Field, field_serializer

from errorscraper.enums import EventPriority, ExecutionStatus

from .event import Event


class TaskResult(BaseModel):
    """Object for result of a task"""

    status: ExecutionStatus = ExecutionStatus.UNSET
    message: str = ""
    task: Optional[str] = None
    parent: Optional[str] = None
    artifacts: list[BaseModel] = Field(default_factory=list)
    events: list[Event] = Field(default_factory=list)
    start_time: datetime.datetime = Field(default_factory=datetime.datetime.now)
    end_time: datetime.datetime = Field(default_factory=datetime.datetime.now)

    @field_serializer("status")
    def serialize_status(self, status: ExecutionStatus, _info) -> str:
        """Use status name when serializing result
        Args:
            status (ExecutionStatus): status enum
        Returns:
            str: status name string
        """
        return status.name

    @property
    def duration(self) -> str | None:
        """return duration of time as a string

        Returns:
            str: duration string
        """
        if self.start_time and self.end_time:
            duration = str((self.end_time - self.start_time))
        else:
            duration = None

        return duration

    def _get_event_summary(self) -> str:
        """Get summary string for artifacts

        Returns:
            str: artifact summary
        """
        error_count = 0
        warning_count = 0

        for event in self.events:
            if event.priority == EventPriority.WARNING:
                warning_count += 1
            elif event.priority >= EventPriority.ERROR:
                error_count += 1

        summary_list = []

        if warning_count:
            summary_list.append(f"{warning_count} warnings")
        if error_count:
            summary_list.append(f"{error_count} errors")

        return "|".join(summary_list)

    def _update_status(self) -> None:
        """Update overall status based on event priority"""
        self.status = ExecutionStatus.OK
        for event in self.events:
            if event.priority >= EventPriority.ERROR:
                self.status = ExecutionStatus.ERROR
                break
            elif event.priority == EventPriority.WARNING:
                self.status = ExecutionStatus.WARNING

    def finalize(self, logger: Optional[logging.Logger] = None) -> None:
        self.end_time = datetime.datetime.now()

        if self.status == ExecutionStatus.UNSET:
            self._update_status()

        if not self.message:
            if self.status == ExecutionStatus.OK:
                self.message = "task completed successfully"
            elif self.status == ExecutionStatus.WARNING:
                self.message = "task completed with warnings"
            elif self.status == ExecutionStatus.NOT_RAN:
                self.message = "task skipped"
            elif self.status == ExecutionStatus.EXECUTION_FAILURE:
                self.message = "task failed to run"
            elif self.status == ExecutionStatus.ERROR:
                self.message = "task detected errors"

        event_summary = self._get_event_summary()
        if event_summary:
            self.message += f" ({event_summary})"

        if logger:
            logger.log(self.status.value, "(%s) %s", self.__class__.__name__, self.message)
