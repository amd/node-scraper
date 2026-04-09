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
import os
from typing import Optional, Union

from nodescraper.base.regexanalyzer import ErrorRegex, RegexAnalyzer, RegexEvent
from nodescraper.enums import ExecutionStatus
from nodescraper.models import TaskResult

from .analyzer_args import RegexSearchAnalyzerArgs
from .regex_search_data import RegexSearchData


class RegexSearchAnalyzer(RegexAnalyzer[RegexSearchData, RegexSearchAnalyzerArgs]):
    """Run user-provided regexes against text loaded from --data (file or directory)."""

    DATA_MODEL = RegexSearchData

    ERROR_REGEX: list[ErrorRegex] = []

    def _build_regex_event(
        self, regex_obj: ErrorRegex, match: Union[str, list[str]], source: str
    ) -> RegexEvent:
        """Augment the default event text with a file path when the origin is a concrete path.

        Args:
            regex_obj: Metadata for the rule that produced the match.
            match: Substring or grouped capture text from the pattern.
            source: Origin label, or an absolute path when matching per file.

        Returns:
            Match record with an extended description when a path-like source is present.
        """
        event = super()._build_regex_event(regex_obj, match, source)
        if source and source != "regex_search":
            event.description = f"{regex_obj.message} [file: {source}]"
        return event

    def analyze_data(
        self,
        data: RegexSearchData,
        args: Optional[RegexSearchAnalyzerArgs] = None,
    ) -> TaskResult:
        """Scan loaded inputs with the given patterns, or mark the task not run if inputs are incomplete.

        Args:
            data: Aggregated and per-file text loaded from the user data path.
            args: Optional pattern list and timing knobs; omitted or empty patterns skip work.

        Returns:
            Work outcome with match events, or a not-run status when patterns are absent.
        """
        if args is None or not args.error_regex:
            self.result.status = ExecutionStatus.NOT_RAN
            self.result.message = (
                "No error_regex patterns provided; nothing to analyze"
                if args is not None
                else "No analysis_args provided; nothing to analyze"
            )
            return self.result

        final_regex = self._convert_and_extend_error_regex(args.error_regex, [])

        if data.files:
            for rel_path in sorted(data.files.keys()):
                file_content = data.files[rel_path]
                abs_source = os.path.normpath(os.path.join(data.data_root, rel_path))
                self.result.events += self.check_all_regexes(
                    content=file_content,
                    source=abs_source,
                    error_regex=final_regex,
                    num_timestamps=args.num_timestamps,
                    interval_to_collapse_event=args.interval_to_collapse_event,
                )
        else:
            self.result.events += self.check_all_regexes(
                content=data.content,
                source=data.data_root or "regex_search",
                error_regex=final_regex,
                num_timestamps=args.num_timestamps,
                interval_to_collapse_event=args.interval_to_collapse_event,
            )
        return self.result
