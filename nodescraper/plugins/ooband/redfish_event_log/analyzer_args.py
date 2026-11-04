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
import re
from datetime import datetime, timezone
from typing import Optional

from pydantic import Field, field_validator

from nodescraper.models import AnalyzerArgs


class RedfishEventLogAnalyzerArgs(AnalyzerArgs):
    """Analyzer args for Redfish LogService entries."""

    since: Optional[datetime] = Field(
        default=None,
        description=(
            "Only analyze entries created at or after this ISO 8601 time (naive values are UTC). "
            "Entries without a parseable Created time are always analyzed."
        ),
    )
    message_id_include: Optional[list[str]] = Field(
        default=None,
        description="If set, only analyze entries whose MessageId matches one of these regexes.",
    )
    message_id_exclude: list[str] = Field(
        default_factory=list,
        description="Skip entries whose MessageId matches any of these regexes.",
    )

    @field_validator("since")
    @classmethod
    def _since_utc(cls, value: Optional[datetime]) -> Optional[datetime]:
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    @field_validator("message_id_include", "message_id_exclude")
    @classmethod
    def _valid_patterns(cls, patterns: Optional[list[str]]) -> Optional[list[str]]:
        for pattern in patterns or []:
            try:
                re.compile(pattern)
            except re.error as exc:
                raise ValueError(f"invalid regex {pattern!r}: {exc}") from exc
        return patterns
