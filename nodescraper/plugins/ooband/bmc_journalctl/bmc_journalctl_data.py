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
"""Data models for BMC journal entries collected with journalctl."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pydantic import AliasChoices, Field, field_validator

from nodescraper.models import DataModel

MICROSECONDS_PER_SECOND = 1_000_000


class JournalctlEntry(DataModel):
    """One parsed journalctl JSON record."""

    timestamp: Optional[datetime] = Field(
        default=None,
        validation_alias=AliasChoices("__REALTIME_TIMESTAMP", "timestamp"),
        description="Record wall-clock time, from the journald __REALTIME_TIMESTAMP field.",
    )
    priority: Optional[int] = Field(
        default=None,
        validation_alias=AliasChoices("PRIORITY", "priority"),
        description="Syslog priority, 0 (emerg) through 7 (debug).",
    )
    message: str = Field(
        default="",
        validation_alias=AliasChoices("MESSAGE", "message"),
        description="The log message text.",
    )
    syslog_identifier: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("SYSLOG_IDENTIFIER", "syslog_identifier"),
        description="Syslog tag of the writing process, e.g. kernel or bmcweb.",
    )
    systemd_unit: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("_SYSTEMD_UNIT", "systemd_unit"),
        description="Systemd unit that produced the record.",
    )
    pid: Optional[int] = Field(
        default=None,
        validation_alias=AliasChoices("_PID", "pid"),
        description="Process id of the writing process.",
    )
    hostname: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("_HOSTNAME", "hostname"),
        description="Hostname recorded by the BMC journal.",
    )
    transport: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("_TRANSPORT", "transport"),
        description="How the record reached journald, e.g. kernel, stdout or journal.",
    )

    @field_validator("timestamp", mode="before")
    @classmethod
    def microseconds_to_datetime(cls, value: object) -> Optional[datetime]:
        if value is None or isinstance(value, datetime):
            return value
        if not isinstance(value, (str, int, float)):
            return None
        try:
            microseconds = int(value)
        except (OverflowError, ValueError):
            if not isinstance(value, str):
                return None
            try:
                iso_value = value[:-1] + "+00:00" if value.endswith("Z") else value
                return datetime.fromisoformat(iso_value)
            except ValueError:
                return None
        return datetime.fromtimestamp(microseconds / MICROSECONDS_PER_SECOND, tz=timezone.utc)

    @field_validator("message", mode="before")
    @classmethod
    def decode_message(cls, value: object) -> str:
        def to_text(item: object) -> str:
            if item is None:
                return ""
            if isinstance(item, list):
                if all(isinstance(byte, int) and 0 <= byte <= 255 for byte in item):
                    return bytes(item).decode("utf-8", errors="replace")
                return " ".join(to_text(value) for value in item)
            return str(item)

        if isinstance(value, list) and not all(
            isinstance(byte, int) and 0 <= byte <= 255 for byte in value
        ):
            return " ".join(to_text(item) for item in value)
        return to_text(value)

    @field_validator("priority", "pid", mode="before")
    @classmethod
    def coerce_optional_int(cls, value: object) -> Optional[int]:
        if value is None or isinstance(value, int):
            return value
        if not isinstance(value, (str, float)):
            return None
        try:
            return int(value)
        except ValueError:
            return None

    def __hash__(self) -> int:
        return hash((self.message, self.priority, self.syslog_identifier))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, JournalctlEntry):
            return NotImplemented
        return (
            self.message == other.message
            and self.priority == other.priority
            and self.syslog_identifier == other.syslog_identifier
        )


class JournalctlData(DataModel):
    """BMC journal entries collected with journalctl, plus how they were collected."""

    entries: list[JournalctlEntry] = Field(default_factory=list)
    mode: str = Field(default="", description="The collection mode that produced these entries.")
    command: str = Field(default="", description="The journalctl command issued on the BMC.")
    truncated: bool = Field(
        default=False,
        description="Whether collection hit the max_entries ceiling.",
    )
