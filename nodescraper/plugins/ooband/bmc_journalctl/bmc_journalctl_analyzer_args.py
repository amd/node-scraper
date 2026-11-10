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
"""Arguments for JournalctlAnalyzer."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import Field

from nodescraper.models import AnalyzerArgs


class JournalctlAnalyzerArgs(AnalyzerArgs):
    """Arguments for BMC journalctl entry analysis."""

    analysis_range_start: Optional[datetime] = Field(
        default=None,
        description="Start of the time window for journal analysis; entries before this are ignored.",
    )
    analysis_range_end: Optional[datetime] = Field(
        default=None,
        description="End of the time window for journal analysis; entries after this are ignored.",
    )
    group: bool = Field(
        default=True,
        description=(
            "Whether to group journal entries that share a message, priority, and syslog identifier."
        ),
    )
