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
import os
from datetime import datetime
from typing import Optional, Union

from pydantic import ConfigDict, Field, field_validator

from nodescraper.models import DataModel


class JournalJsonEntry(DataModel):
    """Data model for journalctl json log entry"""

    model_config = ConfigDict(populate_by_name=True, extra="allow")  # allow extra fields
    TRANSPORT: Optional[str] = Field(None, alias="_TRANSPORT")
    MACHINE_ID: Optional[str] = Field(None, alias="_MACHINE_ID")
    HOSTNAME: Optional[str] = Field(None, alias="_HOSTNAME")
    SYSLOG_IDENTIFIER: Optional[str] = Field(None, alias="SYSLOG_IDENTIFIER")
    CURSOR: Optional[str] = Field(None, alias="__CURSOR")
    SYSLOG_FACILITY: Optional[int] = Field(None, alias="SYSLOG_FACILITY")
    SOURCE_REALTIME_TIMESTAMP: Optional[datetime] = Field(None, alias="_SOURCE_REALTIME_TIMESTAMP")
    REALTIME_TIMESTAMP: Optional[datetime] = Field(None, alias="__REALTIME_TIMESTAMP")
    PRIORITY: int = Field(default=7, alias="PRIORITY")  # Default to DEBUG (7) if not present
    BOOT_ID: Optional[str] = Field(None, alias="_BOOT_ID")
    SOURCE_MONOTONIC_TIMESTAMP: Optional[float] = Field(None, alias="_SOURCE_MONOTONIC_TIMESTAMP")
    MONOTONIC_TIMESTAMP: Optional[float] = Field(None, alias="__MONOTONIC_TIMESTAMP")
    MESSAGE: Union[str, list[str]] = Field(default="", alias="MESSAGE")

    # assume datetime has microseconds
    @field_validator("SOURCE_REALTIME_TIMESTAMP", mode="before")
    @classmethod
    def validate_source_realtime_timestamp(cls, v):
        if v is None:
            return None
        try:
            return datetime.fromisoformat(v)
        except ValueError:
            return datetime.fromtimestamp(float(v) / 1e6)

    # assume datetime has microseconds
    @field_validator("REALTIME_TIMESTAMP", mode="before")
    @classmethod
    def validate_realtime_timestamp(cls, v):
        if v is None:
            return None
        try:
            return datetime.fromisoformat(v)
        except ValueError:
            return datetime.fromtimestamp(float(v) / 1e6)

    @field_validator("SOURCE_MONOTONIC_TIMESTAMP", mode="before")
    @classmethod
    def validate_source_monotonic_timestamp(cls, v):
        if v is None:
            return None
        return float(v)

    @field_validator("MONOTONIC_TIMESTAMP", mode="before")
    @classmethod
    def validate_monotonic_timestamp(cls, v):
        if v is None:
            return None
        return float(v)

    @field_validator("PRIORITY", mode="before")
    @classmethod
    def validate_priority(cls, v):
        priority_map = {
            "EMERG": 0,
            "ALERT": 1,
            "CRIT": 2,
            "ERR": 3,
            "WARNING": 4,
            "NOTICE": 5,
            "INFO": 6,
            "DEBUG": 7,
        }
        if isinstance(v, str):
            return priority_map.get(v.upper(), 7)  # Default to DEBUG if unknown
        return int(v)

    @field_validator("SYSLOG_FACILITY", mode="before")
    @classmethod
    def validate_syslog_facility(cls, v):
        if v is None:
            return None
        return int(v)

    @field_validator("MESSAGE", mode="before")
    @classmethod
    def validate_message(cls, v):
        """Convert MESSAGE field to string or list[str] based on input type"""
        if v is None:
            return ""

        # If it's a list but not all items are strings, convert each item to string
        if isinstance(v, list):
            return [str(item) for item in v]

        # Return string representation for any other type
        return str(v)


class JournalData(DataModel):
    """Data model for journal logs"""

    journal_log: str
    journal_content_json: list[JournalJsonEntry] = Field(default_factory=list)

    def log_model(self, log_path: str):
        """Log data model to a file

        Args:
            log_path (str): log path
        """
        log_name = os.path.join(log_path, "journal.log")
        with open(log_name, "w", encoding="utf-8") as log_filename:
            log_filename.write(self.journal_log)
