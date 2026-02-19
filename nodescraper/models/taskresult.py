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
import json
import logging
import os
from typing import Any, Optional

from pydantic import (
    BaseModel,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

from nodescraper.enums import EventPriority, ExecutionStatus
from nodescraper.utils import get_unique_filename, pascal_to_snake

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

    @model_validator(mode="before")
    @classmethod
    def _source_source_type_aliases(cls, data: Any) -> Any:
        """Accept source/source_type as aliases for task/parent"""
        if isinstance(data, dict):
            data = dict(data)
            if "source" in data and "task" not in data:
                data["task"] = data.pop("source")
            if "source_type" in data and "parent" not in data:
                data["parent"] = data.pop("source_type")
        return data

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

    @field_validator("status", mode="before")
    @classmethod
    def validate_status(cls, v: Any):
        """Validator to ensure `status` is a valid ExecutionStatus enum.

        Args:
            v (Any): The input value to validate (can be str or ExecutionStatus).

        Returns:
            ExecutionStatus: The validated enum value.

        Raises:
            ValueError: If the string is not a valid enum name.
        """
        if isinstance(v, ExecutionStatus):
            return v
        if isinstance(v, str):
            try:
                return ExecutionStatus[v]
            except KeyError as err:
                raise ValueError(f"Unknown status name: {v!r}") from err
        return v

    @property
    def duration(self) -> Optional[str]:
        """return duration of time as a string

        Returns:
            str: duration string
        """
        if self.start_time and self.end_time:
            duration = str((self.end_time - self.start_time))
        else:
            duration = None

        return duration

    @property
    def source(self) -> str:
        """Task/source name."""
        return self.task or ""

    @source.setter
    def source(self, value: str) -> None:
        """Set task from source"""
        self.task = value if value else None

    @property
    def source_type(self) -> str:
        """Task/source type."""
        return self.parent or ""

    @source_type.setter
    def source_type(self, value: str) -> None:
        """Set parent from source_type"""
        self.parent = value if value else None

    @property
    def summary_dict(self) -> dict:
        """Summary dict for logging/display (task_name, task_type, task_result, event_count, duration)."""
        return {
            "task_name": self.source or self.parent or "",
            "task_type": self.source_type or self.task or "",
            "task_result": self.status.name if self.status else None,
            "event_count": len(self.events),
            "duration": self.duration,
        }

    @property
    def summary_str(self) -> str:
        """Message string for display."""
        return self.message or ""

    def log_result(self, log_path: str) -> None:
        """Write result, artifacts, and events to log_path. Events are merged into a single events.json."""
        from nodescraper.connection.inband import BaseFileArtifact

        os.makedirs(log_path, exist_ok=True)

        with open(os.path.join(log_path, "result.json"), "w", encoding="utf-8") as log_file:
            log_file.write(self.model_dump_json(exclude={"artifacts", "events"}, indent=2))

        artifact_map: dict[str, list[dict[str, Any]]] = {}
        for artifact in self.artifacts:
            if isinstance(artifact, BaseFileArtifact):
                artifact.log_model(log_path)
            else:
                name = f"{pascal_to_snake(artifact.__class__.__name__)}s"
                if name in artifact_map:
                    artifact_map[name].append(artifact.model_dump(mode="json"))
                else:
                    artifact_map[name] = [artifact.model_dump(mode="json")]

        for name, artifacts in artifact_map.items():
            log_name = get_unique_filename(log_path, f"{name}.json")
            with open(os.path.join(log_path, log_name), "w", encoding="utf-8") as log_file:
                json.dump(artifacts, log_file, indent=2)

        if self.events:
            event_log = os.path.join(log_path, "events.json")
            new_events = [e.model_dump(mode="json", exclude_none=True) for e in self.events]
            existing_events = []
            if os.path.isfile(event_log):
                try:
                    with open(event_log, "r", encoding="utf-8") as f:
                        existing_events = json.load(f)
                    if not isinstance(existing_events, list):
                        existing_events = []
                except (json.JSONDecodeError, OSError):
                    existing_events = []
            all_events = existing_events + new_events
            with open(event_log, "w", encoding="utf-8") as log_file:
                json.dump(all_events, log_file, indent=2)

    def _get_event_summary(self) -> str:
        """Get summary string for events

        Returns:
            str: event summary with counts and descriptions
        """
        error_msg_counts: dict[str, int] = {}
        warning_msg_counts: dict[str, int] = {}

        for event in self.events:
            if event.priority == EventPriority.WARNING:
                warning_msg_counts[event.description] = (
                    warning_msg_counts.get(event.description, 0) + 1
                )
            elif event.priority >= EventPriority.ERROR:
                error_msg_counts[event.description] = error_msg_counts.get(event.description, 0) + 1

        summary_parts = []

        if warning_msg_counts:
            total_warnings = sum(warning_msg_counts.values())
            warning_details = [
                f"{msg} (x{count})" if count > 1 else msg
                for msg, count in warning_msg_counts.items()
            ]
            summary_parts.append(f"{total_warnings} warnings: {', '.join(warning_details)}")

        if error_msg_counts:
            total_errors = sum(error_msg_counts.values())
            error_details = [
                f"{msg} (x{count})" if count > 1 else msg for msg, count in error_msg_counts.items()
            ]
            summary_parts.append(f"{total_errors} errors: {', '.join(error_details)}")

        return "; ".join(summary_parts)

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
