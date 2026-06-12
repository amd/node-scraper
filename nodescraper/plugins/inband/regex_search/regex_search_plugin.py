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
from typing import Optional, Union

from nodescraper.base import InBandDataPlugin
from nodescraper.enums import EventPriority
from nodescraper.models import CollectorArgs, TaskResult

from .analyzer_args import RegexSearchAnalyzerArgs
from .regex_search_analyzer import RegexSearchAnalyzer
from .regex_search_data import RegexSearchData


class RegexSearchPlugin(InBandDataPlugin[RegexSearchData, CollectorArgs, RegexSearchAnalyzerArgs]):
    """Analyzer-only plugin: search user regexes against a file or directory (--data)."""

    DATA_MODEL = RegexSearchData
    ANALYZER = RegexSearchAnalyzer

    def analyze(
        self,
        max_event_priority_level: Optional[Union[EventPriority, str]] = EventPriority.CRITICAL,
        analysis_args: Optional[Union[RegexSearchAnalyzerArgs, dict]] = None,
        data: Optional[Union[str, dict, RegexSearchData]] = None,
    ) -> TaskResult:
        if analysis_args is None:
            missing_error_regex = True
        elif isinstance(analysis_args, RegexSearchAnalyzerArgs):
            missing_error_regex = not bool(analysis_args.error_regex)
        elif isinstance(analysis_args, dict):
            er = analysis_args.get("error_regex")
            missing_error_regex = er is None or er == []
        else:
            missing_error_regex = True
        if missing_error_regex:
            self.logger.warning(
                "RegexSearchPlugin: analysis args need to be provided for the analyzer to run "
                "(e.g. --error-regex for each pattern)."
            )
        return super().analyze(
            max_event_priority_level=max_event_priority_level,
            analysis_args=analysis_args,
            data=data,
        )
