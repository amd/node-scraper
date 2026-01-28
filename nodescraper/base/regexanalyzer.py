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
import datetime
import re
from typing import Optional, Union

from pydantic import BaseModel

from nodescraper.enums import EventCategory, EventPriority
from nodescraper.generictypes import TAnalyzeArg, TDataModel
from nodescraper.interfaces.dataanalyzertask import DataAnalyzer
from nodescraper.models.event import Event


class ErrorRegex(BaseModel):
    regex: re.Pattern
    message: str
    event_category: Union[str, EventCategory] = EventCategory.UNKNOWN
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

    # Class variable for timestamp pattern - can be overridden in subclasses
    TIMESTAMP_PATTERN: re.Pattern = re.compile(r"(\d{4}-\d+-\d+T\d+:\d+:\d+,\d+[+-]\d+:\d+)")

    def _extract_timestamp_from_match_position(
        self, content: str, match_start: int
    ) -> Optional[str]:
        """Extract timestamp from the line where a regex match starts.

        Args:
            content (str): Full content being analyzed
            match_start (int): Start position of the regex match

        Returns:
            Optional[str]: Extracted timestamp string or None
        """
        # Get the line where the match starts
        line_start = content.rfind("\n", 0, match_start) + 1
        line_end = content.find("\n", match_start)
        if line_end == -1:
            line_end = len(content)

        first_line = content[line_start:line_end]

        # Extract timestamp from first line only using class pattern
        timestamp_match = self.TIMESTAMP_PATTERN.search(first_line)
        return timestamp_match.group(1) if timestamp_match else None

    def _convert_and_extend_error_regex(
        self, custom_regex: Optional[list[ErrorRegex] | list[dict]], base_regex: list[ErrorRegex]
    ) -> list[ErrorRegex]:
        """Convert custom error patterns and extend base ERROR_REGEX.

        Supports two input formats:
        - ErrorRegex objects directly
        - Dicts with regex/message/category/priority that get converted to ErrorRegex

        Args:
            custom_regex: Optional list of custom error patterns (ErrorRegex objects or dicts)
            base_regex: Base list of ErrorRegex patterns to extend

        Returns:
            Extended list of ErrorRegex objects (custom patterns + base patterns)

        Example:
            custom = [
                {"regex": r"my-error.*", "message": "Custom error", "event_category": "SW_DRIVER"}
            ]
            extended = analyzer._convert_and_extend_error_regex(custom, analyzer.ERROR_REGEX)
        """
        if not custom_regex or not isinstance(custom_regex, list):
            return list(base_regex)

        converted_regex = []
        for item in custom_regex:
            if isinstance(item, ErrorRegex):
                converted_regex.append(item)
            elif isinstance(item, dict):
                # Convert dict to ErrorRegex
                item["regex"] = re.compile(item["regex"])
                if "event_category" in item:
                    item["event_category"] = EventCategory(item["event_category"])
                if "event_priority" in item:
                    item["event_priority"] = EventPriority(item["event_priority"])
                converted_regex.append(ErrorRegex(**item))

        return converted_regex + list(base_regex)

    def _build_regex_event(
        self, regex_obj: ErrorRegex, match: Union[str, list[str]], source: str
    ) -> RegexEvent:
        """Build a RegexEvent object from a regex match and source.

        Args:
            regex_obj (ErrorRegex): regex object containing the regex pattern, message, category, and priorit
            match (
        Union[str, list[str]]): matched content from the regex
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
        self,
        content: str,
        source: str,
        error_regex: list[ErrorRegex],
        group: bool = True,
        num_timestamps: int = 3,
        interval_to_collapse_event: int = 60,
    ) -> list[RegexEvent]:
        """Iterate over all ERROR_REGEX and check content for any matches

        Enhanced with timestamp-based event collapsing:
        - Extracts timestamps from matched lines
        - Collapses events within interval_to_collapse_event seconds
        - Prunes timestamp lists to keep first N and last N timestamps

        Args:
            content (str): content to match regex on
            source (str): descriptor for content
            error_regex (list[ErrorRegex]): list of regex objects to match
            group (bool, optional): flag to control whether matches should be grouped together. Defaults to True.
            num_timestamps (int, optional): maximum number of timestamps to keep for each event. Defaults to 3.
            interval_to_collapse_event (int, optional): time interval in seconds to collapse events. Defaults to 60.

        Returns:
            list[RegexEvent]: list of regex event objects
        """

        regex_map: dict[str, RegexEvent] = {}
        regex_event_list: list[RegexEvent] = []

        def _is_within_interval(new_timestamp_str: str, existing_timestamps: list[str]) -> bool:
            """Check if new timestamp is within the specified interval of any existing timestamp"""
            try:
                new_dt = datetime.datetime.fromisoformat(new_timestamp_str.replace(",", "."))
            except Exception as e:
                self.logger.warning(
                    f"WARNING: Failed to parse date from timestamp: {new_timestamp_str}. Error: {e}"
                )
                return False

            if not new_dt:
                return False

            for existing_ts in existing_timestamps:
                try:
                    existing_dt = datetime.datetime.fromisoformat(existing_ts.replace(",", "."))
                    if (
                        existing_dt
                        and abs((new_dt - existing_dt).total_seconds()) < interval_to_collapse_event
                    ):
                        return True
                except Exception:
                    continue
            return False

        for error_regex_obj in error_regex:
            for match_obj in error_regex_obj.regex.finditer(content):
                # Extract timestamp from the line where match occurs
                timestamp = self._extract_timestamp_from_match_position(content, match_obj.start())

                match = match_obj.groups() if match_obj.groups() else match_obj.group(0)

                # Process multi-line matches
                if isinstance(match, str) and "\n" in match:
                    match = match.strip().split("\n")

                # filter out empty string
                if isinstance(match, tuple) or isinstance(match, list):
                    match = [match_val for match_val in match if match_val]
                    if len(match) == 1:
                        match = match[0]

                # Create match key for grouping
                match_key = str(match)

                if group and match_key in regex_map:
                    # Increment count for existing match
                    existing_event = regex_map[match_key]
                    existing_event.count += 1

                    # Add timestamp to timestamps list if we have one
                    if timestamp:
                        timestamps_list = existing_event.data.get("timestamps", [])
                        # Check if new timestamp is within the specified interval of existing ones
                        if not _is_within_interval(timestamp, timestamps_list):
                            timestamps_list.append(timestamp)
                            existing_event.data["timestamps"] = timestamps_list

                elif group:
                    # Create new grouped event
                    new_event = self._build_regex_event(error_regex_obj, match, source)

                    # Add timestamp information
                    if timestamp:
                        new_event.data["timestamps"] = [timestamp]

                    regex_map[match_key] = new_event

                else:
                    # Create individual event (no grouping)
                    new_event = self._build_regex_event(error_regex_obj, match, source)

                    # Add single timestamp
                    if timestamp:
                        new_event.data["timestamp"] = timestamp

                    regex_event_list.append(new_event)

        all_events = list(regex_map.values()) if group else regex_event_list

        # Prune timestamp lists to keep only first N and last N timestamps
        for event in all_events:
            timestamps_list = event.data.get("timestamps", [])
            if isinstance(timestamps_list, list) and len(timestamps_list) > 2 * num_timestamps:
                # Keep first num_timestamps and last num_timestamps
                pruned_timestamps = (
                    timestamps_list[:num_timestamps] + timestamps_list[-num_timestamps:]
                )
                event.data["timestamps"] = pruned_timestamps

        return all_events
