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
from typing import Any, Optional

from pydantic import Field

from nodescraper.models import AnalyzerArgs


class RegexSearchAnalyzerArgs(AnalyzerArgs):
    """Arguments for RegexSearchAnalyzer (dict items match Dmesg-style error_regex)."""

    error_regex: Optional[list[dict[str, Any]]] = Field(
        default=None,
        description=(
            "Regex patterns to search for; each dict may include regex (str), message, "
            "event_category, event_priority (same as Dmesg analyzer error_regex). "
        ),
    )
    interval_to_collapse_event: int = Field(
        default=60,
        description="Seconds within which repeated events are collapsed into one.",
    )
    num_timestamps: int = Field(
        default=3,
        description="Number of timestamps to include per event in output.",
    )
