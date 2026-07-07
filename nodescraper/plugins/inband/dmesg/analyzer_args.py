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

from nodescraper.base.match_ignore import IgnoreMatchRuleSpec
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
    priority_override_rules: Optional[list[dict]] = Field(
        default=None,
        description=(
            "Rules to override the priority of matched ErrorRegex objects. "
            "Each rule is a dict where all keys except 'new_priority' and 'match_all' "
            "are filter fields matched against ErrorRegex attributes. "
            "'new_priority' must be an EventPriority name (e.g. 'WARNING', 'ERROR') "
            "or 'NO_CHANGE' to leave the priority unchanged."
        ),
    )
    mce_threshold: Optional[int] = Field(
        default=None,
        description=(
            "When set, raise ERROR if correctable MCE/RAS error count for any component "
            "(CPU, GPU BDF/block, etc.) reaches or exceeds this value."
        ),
    )
    ignore_match_rules: Optional[list[IgnoreMatchRuleSpec]] = Field(
        default=None,
        description=(
            "Rules that skip regex matches during analysis. Each rule may use line_regex, "
            "match_regex, message, and/or mce_banks. Within a rule all specified fields must "
            "match; any matching rule suppresses the hit. mce_banks accepts bank ids and "
            'inclusive ranges such as "60-63".'
        ),
    )
