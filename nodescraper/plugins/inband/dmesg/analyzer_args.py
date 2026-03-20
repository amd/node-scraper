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
from typing import Optional, Union

from pydantic import Field

from nodescraper.base.regexanalyzer import ErrorRegex
from nodescraper.models import TimeRangeAnalysisArgs


class DmesgAnalyzerArgs(TimeRangeAnalysisArgs):
    check_unknown_dmesg_errors: Optional[bool] = Field(
        default=True,
        description="If True, treat unknown/unmatched dmesg error lines as failures.",
    )
    exclude_category: Optional[set[str]] = Field(
        default=None,
        description="Set of error categories to exclude from analysis.",
    )
    interval_to_collapse_event: int = Field(
        default=60,
        description="Seconds within which repeated events are collapsed into one (for rate limiting).",
    )
    num_timestamps: int = Field(
        default=3,
        description="Number of timestamps to include per event in output.",
    )
    error_regex: Optional[Union[list[ErrorRegex], list[dict]]] = Field(
        default=None,
        description="Custom error regex patterns; each item can be ErrorRegex or dict with category/pattern.",
    )
