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
import datetime
import logging
from typing import Optional

from pydantic import BaseModel, Field, field_serializer

from nodescraper.enums import EventPriority, ExecutionStatus

from .event import Event

STATUS_LOG_LEVEL_MAP = {
    ExecutionStatus.UNSET: logging.INFO,
    ExecutionStatus.NOT_RAN: logging.INFO,
    ExecutionStatus.OK: logging.INFO,
    ExecutionStatus.WARNING: logging.WARNING,
    ExecutionStatus.ERROR: logging.ERROR,
    ExecutionStatus.EXECUTION_FAILURE: logging.CRITICAL,
}


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
        """Finalize the task result by setting end time, updating status, and logging
        the result.

        Args:
            logger (Optional[logging.Logger], optional): python logger instance. Defaults to None.
        """
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
            logger.log(
                STATUS_LOG_LEVEL_MAP.get(self.status, logging.INFO),
                "(%s) %s",
                self.parent,
                self.message,
            )
