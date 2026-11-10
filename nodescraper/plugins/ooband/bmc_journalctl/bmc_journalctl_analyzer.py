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
"""Analyzer for BMC journal entries collected with journalctl."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, TypedDict

from nodescraper.enums import EventCategory, EventPriority
from nodescraper.interfaces import DataAnalyzer
from nodescraper.models import TaskResult

from .bmc_journalctl_analyzer_args import JournalctlAnalyzerArgs
from .bmc_journalctl_data import JournalctlData, JournalctlEntry

MAX_ERROR_PRIORITY = 3
WARNING_PRIORITY = 4
MESSAGE_EXCERPT_LENGTH = 120


class JournalEvent(TypedDict):
    count: int
    first_occurrence: Optional[datetime]
    last_occurrence: Optional[datetime]


class JournalctlAnalyzer(DataAnalyzer[JournalctlData, JournalctlAnalyzerArgs]):
    """Check BMC journal entries for errors based on syslog priority.

    Entries at notice level (5) or below are not reported. An entry with no priority
    is treated as an error to avoid silently dropping unclassifiable records.
    """

    DATA_MODEL = JournalctlData
    ANALYZER_ARGS = JournalctlAnalyzerArgs

    DOCUMENTATION_ANALYSIS_ITEMS: tuple[str, ...] = (
        "Syslog priority 0-3 (emerg/alert/crit/err) is reported as ERROR, 4 (warning) as WARNING.",
        "Entries with no priority are treated as ERROR.",
        "When analysis_args.group is true (default), matching entries are collapsed with a count.",
        "analysis_args.analysis_range_start/end limits which entries are analyzed.",
    )

    @staticmethod
    def priority_to_event_priority(priority: Optional[int]) -> EventPriority:
        if priority is None:
            return EventPriority.ERROR
        if priority <= MAX_ERROR_PRIORITY:
            return EventPriority.ERROR
        if priority == WARNING_PRIORITY:
            return EventPriority.WARNING
        return EventPriority.INFO

    @staticmethod
    def describe(entry: JournalctlEntry) -> str:
        excerpt = entry.message[:MESSAGE_EXCERPT_LENGTH]
        if len(entry.message) > MESSAGE_EXCERPT_LENGTH:
            excerpt = f"{excerpt}..."
        return (
            f"BMC journal entry with syslog priority '{entry.priority}' "
            f"from '{entry.syslog_identifier}': {excerpt}"
        )

    @staticmethod
    def filter_entries(
        entries: list[JournalctlEntry],
        analysis_range_start: Optional[datetime] = None,
        analysis_range_end: Optional[datetime] = None,
    ) -> list[JournalctlEntry]:
        if analysis_range_start is not None and analysis_range_start.tzinfo is None:
            analysis_range_start = analysis_range_start.replace(tzinfo=timezone.utc)
        if analysis_range_end is not None and analysis_range_end.tzinfo is None:
            analysis_range_end = analysis_range_end.replace(tzinfo=timezone.utc)

        def in_range(entry: JournalctlEntry) -> bool:
            if entry.timestamp is None:
                return True
            if analysis_range_start is not None and entry.timestamp < analysis_range_start:
                return False
            if analysis_range_end is not None and entry.timestamp > analysis_range_end:
                return False
            return True

        return [entry for entry in entries if in_range(entry)]

    def analyze_entries_by_priority(self, entries: list[JournalctlEntry], group: bool) -> None:
        event_map: dict[JournalctlEntry, JournalEvent] = {}

        for entry in entries:
            entry_priority = self.priority_to_event_priority(entry.priority)
            if entry_priority == EventPriority.INFO:
                continue
            if not group:
                self._log_event(
                    category=EventCategory.PLATFORM,
                    description=self.describe(entry),
                    priority=entry_priority,
                    data={
                        "Message": entry.message,
                        "Priority": entry.priority,
                        "Identifier": entry.syslog_identifier,
                        "Unit": entry.systemd_unit,
                        "Timestamp": entry.timestamp,
                    },
                    console_log=False,
                )
            elif entry not in event_map:
                event_map[entry] = {
                    "count": 1,
                    "first_occurrence": entry.timestamp,
                    "last_occurrence": entry.timestamp,
                }
            else:
                event_data = event_map[entry]
                event_data["count"] += 1
                if entry.timestamp is not None:
                    first = event_data["first_occurrence"]
                    last = event_data["last_occurrence"]
                    if first is None or entry.timestamp < first:
                        event_data["first_occurrence"] = entry.timestamp
                    if last is None or entry.timestamp > last:
                        event_data["last_occurrence"] = entry.timestamp

        for entry, event_data in event_map.items():
            self._log_event(
                category=EventCategory.PLATFORM,
                description=self.describe(entry),
                priority=self.priority_to_event_priority(entry.priority),
                data={
                    "Message": entry.message,
                    "Priority": entry.priority,
                    "Identifier": entry.syslog_identifier,
                    "Unit": entry.systemd_unit,
                    **event_data,
                },
                console_log=False,
            )

    def analyze_data(
        self,
        data: JournalctlData,
        args: Optional[JournalctlAnalyzerArgs] = None,
    ) -> TaskResult:
        if args is None:
            args = JournalctlAnalyzerArgs()

        if args.analysis_range_start or args.analysis_range_end:
            entries = self.filter_entries(
                data.entries, args.analysis_range_start, args.analysis_range_end
            )
        else:
            entries = data.entries

        self.analyze_entries_by_priority(entries, args.group)
        return self.result
