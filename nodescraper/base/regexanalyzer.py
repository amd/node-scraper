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
import re

from pydantic import BaseModel

from nodescraper.enums import EventCategory, EventPriority
from nodescraper.generictypes import TAnalyzeArg, TDataModel
from nodescraper.interfaces.dataanalyzertask import DataAnalyzer
from nodescraper.models.event import Event


class ErrorRegex(BaseModel):
    regex: re.Pattern
    message: str
    event_category: str | EventCategory = EventCategory.UNKNOWN
    event_priority: EventPriority = EventPriority.ERROR


class RegexEvent(Event):
    @property
    def count(self) -> int:
        return int(self.data.get("count", 0))

    @count.setter
    def count(self, val: int):
        self.data["count"] = val


class RegexAnalyzer(DataAnalyzer[TDataModel, TAnalyzeArg]):
    """Parent class for all regex based data analyzers."""

    def _build_regex_event(
        self, regex_obj: ErrorRegex, match: str | list[str], source: str
    ) -> RegexEvent:
        """Build a RegexEvent object from a regex match and source.

        Args:
            regex_obj (ErrorRegex): regex object containing the regex pattern, message, category, and priorit
            match (str | list[str]): matched content from the regex
            source (str): descriptor for the content where the match was found

        Returns:
            RegexEvent: an instance of RegexEvent containing the match details
        """
        return RegexEvent(
            description=regex_obj.message,
            category=regex_obj.event_category,
            priority=regex_obj.event_priority,
            data={
                "match_content": match,
                "source": source,
                "count": 1,
                "task_name": self.__class__.__name__,
                "task_type": self.TASK_TYPE,
            },
        )

    def check_all_regexes(
        self, content: str, source: str, error_regex: list[ErrorRegex], group=True
    ) -> list[RegexEvent]:
        """Iterate over all ERROR_REGEX and check content for any matches

        Args:
            content (str): content to match regex on
            source (str): descriptor for content
            error_regex (list[ErrorRegex]): list of regex objects to match
            group (bool, optional): flag to control whether matches should be grouped together. Defaults to True.

        Returns:
            list[RegexEvent]: list of regex event objects
        """

        regex_map: dict[str, RegexEvent] = {}
        regex_event_list: list[RegexEvent] = []

        for error_regex_obj in error_regex:
            for match in error_regex_obj.regex.findall(content):
                if isinstance(match, str) and "\n" in match:
                    match = match.strip().split("\n")

                # filter out empty string
                if isinstance(match, tuple) or isinstance(match, list):
                    match = [match_val for match_val in match if match_val]
                    if len(match) == 1:
                        match = match[0]

                if group and str(match) in regex_map:
                    regex_map[str(match)].count += 1
                elif group:
                    regex_map[str(match)] = self._build_regex_event(error_regex_obj, match, source)
                else:
                    regex_event_list.append(self._build_regex_event(error_regex_obj, match, source))

        return list(regex_map.values()) if group else regex_event_list
