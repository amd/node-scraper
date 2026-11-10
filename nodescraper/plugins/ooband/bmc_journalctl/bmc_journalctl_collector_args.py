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
"""Arguments for JournalctlCollector."""

from __future__ import annotations

from enum import Enum
from typing import Optional, TypeVar

from pydantic import Field, field_validator, model_validator

from nodescraper.models import CollectorArgs

DEFAULT_LINE_COUNT = 20000
MAX_ENTRIES_CEILING = 50000

TModeArg = TypeVar("TModeArg")


class JournalctlMode(str, Enum):
    """How JournalctlCollector selects the slice of journal to collect."""

    ALL = "all"
    LAST_LINES = "last_lines"
    FIRST_LINES = "first_lines"
    LINE_RANGE = "line_range"
    SINCE = "since"
    UNTIL = "until"
    TIME_RANGE = "time_range"
    UNIT = "unit"
    BOOT = "boot"


REQUIRED_FIELDS_BY_MODE: dict[JournalctlMode, tuple[str, ...]] = {
    JournalctlMode.ALL: (),
    JournalctlMode.LAST_LINES: ("line_count",),
    JournalctlMode.FIRST_LINES: ("line_count",),
    JournalctlMode.LINE_RANGE: ("line_start", "line_end"),
    JournalctlMode.SINCE: ("collect_since",),
    JournalctlMode.UNTIL: ("collect_until",),
    JournalctlMode.TIME_RANGE: ("collect_since", "collect_until"),
    JournalctlMode.UNIT: ("unit",),
    JournalctlMode.BOOT: ("boots",),
}


class JournalctlCollectorArgs(CollectorArgs):
    """Arguments for JournalctlCollector."""

    mode: JournalctlMode = Field(
        default=JournalctlMode.LAST_LINES,
        description="Which slice of the BMC journal to collect.",
    )
    priority: Optional[str] = Field(
        default=None,
        description=(
            "Maximum syslog priority to collect, passed to journalctl -p. "
            "Null collects every priority, including debug."
        ),
    )
    line_count: int = Field(
        default=DEFAULT_LINE_COUNT,
        gt=0,
        description=(
            "Entry count for last_lines (newest), first_lines (oldest), and unit (newest)."
        ),
    )
    line_start: Optional[int] = Field(
        default=None,
        gt=0,
        description="First entry to collect in line_range mode, counting from the oldest entry.",
    )
    line_end: Optional[int] = Field(
        default=None,
        gt=0,
        description="Last entry to collect in line_range mode, counting from the oldest entry.",
    )
    collect_since: Optional[str] = Field(
        default=None,
        description="Collect entries at or after this time, for since and time_range modes (ISO 8601).",
    )
    collect_until: Optional[str] = Field(
        default=None,
        description="Collect entries at or before this time, for until and time_range modes (ISO 8601).",
    )
    unit: Optional[list[str]] = Field(
        default=None,
        description=(
            "Systemd unit(s) to collect in unit mode, for example mctpd.service "
            'or ["mctpd.service", "pldmd.service"]. A single string is accepted '
            "and wrapped in a list. Each unit contributes its newest line_count entries, "
            "and the combined result is cut to max_entries."
        ),
    )

    @field_validator("unit", mode="before")
    @classmethod
    def wrap_single_unit(cls, value: object) -> Optional[list[str]]:
        if value is None:
            return None
        if isinstance(value, str):
            return [value]
        return value  # type: ignore[return-value]

    boots: int = Field(
        default=1,
        gt=0,
        description="Number of most recent boots to collect in boot mode; 1 is the current boot.",
    )
    max_entries: int = Field(
        default=MAX_ENTRIES_CEILING,
        gt=0,
        description="Hard ceiling on entries returned by any mode.",
    )

    @model_validator(mode="after")
    def check_fields_required_by_mode(self) -> JournalctlCollectorArgs:
        missing = [
            name for name in REQUIRED_FIELDS_BY_MODE[self.mode] if getattr(self, name, None) is None
        ]
        if missing:
            raise ValueError(f"mode '{self.mode.value}' requires: {', '.join(missing)}")
        if self.mode is JournalctlMode.LINE_RANGE:
            if self.line_start is not None and self.line_end is not None:
                if self.line_start > self.line_end:
                    raise ValueError("line_start must not be greater than line_end")
        return self

    def require(self, value: Optional[TModeArg], field: str) -> TModeArg:
        if value is None:
            raise ValueError(f"mode '{self.mode.value}' requires {field}")
        return value
