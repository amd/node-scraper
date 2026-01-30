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
from datetime import datetime
from typing import Optional, TypedDict

from nodescraper.enums import EventCategory, EventPriority, ExecutionStatus
from nodescraper.interfaces import DataAnalyzer
from nodescraper.models import TaskResult

from .analyzer_args import JournalAnalyzerArgs
from .journaldata import JournalData, JournalJsonEntry


class JournalEvent(TypedDict):
    count: int
    first_occurrence: datetime
    last_occurrence: datetime


class JournalPriority:
    EMERGENCY = 0
    ALERT = 1
    CRITICAL = 2
    ERROR = 3
    WARNING = 4
    NOTICE = 5
    INFO = 6
    DEBUG = 7


class JournalAnalyzer(DataAnalyzer[JournalData, JournalAnalyzerArgs]):
    """Check journalctl for errors"""

    DATA_MODEL = JournalData

    @classmethod
    def filter_journal(
        cls,
        journal_content_json: list[JournalJsonEntry],
        analysis_range_start: Optional[datetime] = None,
        analysis_range_end: Optional[datetime] = None,
    ) -> list[JournalJsonEntry]:
        """Filter a journal log by date

        Args:
            journal_content_json (list[JournalJsonEntry]): unfiltered journal log
            analysis_range_start (Optional[datetime], optional): start of analysis range. Defaults to None.
            analysis_range_end (Optional[datetime], optional): end of analysis range. Defaults to None.

        Returns:
            list[JournalJsonEntry]: filtered journal log
        """

        filtered_journal = []

        found_start = False if analysis_range_start else True

        # Parse through the journal log and filter by date
        for entry in journal_content_json:
            date = entry.REALTIME_TIMESTAMP

            # Skip entries without valid timestamp
            if date is None:
                continue

            if analysis_range_start and not found_start and date >= analysis_range_start:
                found_start = True
            elif analysis_range_end and date >= analysis_range_end:
                break

            # only read entries after starting timestamp is found, ignore entries that do not have valid date
            if found_start:
                filtered_journal.append(entry)

        return filtered_journal

    def _priority_to_entry_priority(self, priority: int) -> EventPriority:
        if priority <= JournalPriority.ERROR:
            entry_priority = EventPriority.ERROR
        elif priority == JournalPriority.WARNING:
            entry_priority = EventPriority.WARNING
        elif priority >= JournalPriority.NOTICE:
            entry_priority = EventPriority.INFO
        else:
            # Unknown?
            entry_priority = EventPriority.ERROR
        return entry_priority

    def _analyze_journal_entries_by_priority(
        self, journal_content_json: list[JournalJsonEntry], priority: int, group: bool
    ) -> None:
        """Analyze a list of Journal Entries for a priority.
        if WARNING, CRITICAL or it is unknown then log an error/warning Journal Entry.
        Parameters
        ----------
        journal_content_json : list[JournalJsonEntry]
            List of JournalJsonEntry to analyze
        priority : int
            Priority threshold to check against
        group : bool
            Whether to group similar entries
        """
        # Use a tuple of (message, priority) as the key instead of the JournalJsonEntry object
        journal_event_map: dict[tuple[str, int], JournalEvent] = {}

        # Check against journal log priority levels. emergency(0), alert(1), critical(2), error(3), warning(4), notice(5), info(6), debug(7)
        for entry in journal_content_json:
            if entry.PRIORITY <= priority:
                self.result.status = ExecutionStatus.ERROR
                if not group:
                    entry_dict = entry.model_dump()  # Convert JournalJsonEntry to dictionary
                    entry_dict["task_name"] = self.__class__.__name__
                    self._log_event(
                        category=EventCategory.OS,
                        description="Journal log entry with priority level %s" % entry.PRIORITY,
                        data=entry_dict,
                        priority=self._priority_to_entry_priority(entry.PRIORITY),
                        console_log=False,
                    )
                else:
                    # Handle MESSAGE as either string or list
                    message = entry.MESSAGE
                    if isinstance(message, list):
                        message = " ".join(message)

                    # Create a tuple key from message and priority
                    entry_key = (message, entry.PRIORITY)
                    if journal_event_map.get(entry_key) is None:
                        journal_event_map[entry_key] = {
                            "count": 1,
                            "first_occurrence": (
                                entry.REALTIME_TIMESTAMP
                                if entry.REALTIME_TIMESTAMP
                                else datetime.fromtimestamp(0)
                            ),
                            "last_occurrence": (
                                entry.REALTIME_TIMESTAMP
                                if entry.REALTIME_TIMESTAMP
                                else datetime.fromtimestamp(0)
                            ),
                        }
                    else:
                        journal_event_map[entry_key]["count"] += 1
                        if entry.REALTIME_TIMESTAMP:
                            journal_event_map[entry_key][
                                "last_occurrence"
                            ] = entry.REALTIME_TIMESTAMP

        # log all events that were grouped
        if group:
            for (message, entry_priority), event_data in journal_event_map.items():
                self._log_event(
                    category=EventCategory.OS,
                    description="Journal entries found in OS journal log",
                    priority=self._priority_to_entry_priority(entry_priority),
                    data={
                        "message": message,
                        "priority": entry_priority,
                        "count": event_data["count"],
                        "first_occurrence": event_data["first_occurrence"],
                        "last_occurrence": event_data["last_occurrence"],
                    },
                    console_log=False,
                )

    def analyze_data(
        self, data: JournalData, args: Optional[JournalAnalyzerArgs] = None
    ) -> TaskResult:
        """Analyze the OS journal log for errors

        Parameters
        ----------
        data : JournalData
            Journal data to analyze
        args : Optional[JournalAnalyzerArgs], optional
            Analysis arguments, by default None

        Returns
        -------
        TaskResult
            A TaskResult object containing the result of the analysis
            If journal log entries are found ExecutionStatus.OK
            If journal log entries are found with priority level less than or equal to check_priority ExecutionStatus.ERROR
        """
        if args is None:
            args = JournalAnalyzerArgs()

        journal_content_json = data.journal_content_json

        # Filter by time range if specified
        if args.analysis_range_start or args.analysis_range_end:
            self.logger.info(
                "Filtering journal log using range %s - %s",
                args.analysis_range_start,
                args.analysis_range_end,
            )
            journal_content_json = self.filter_journal(
                journal_content_json=journal_content_json,
                analysis_range_start=args.analysis_range_start,
                analysis_range_end=args.analysis_range_end,
            )

        self.result.status = ExecutionStatus.OK

        if args.check_priority is not None:
            self._analyze_journal_entries_by_priority(
                journal_content_json, args.check_priority, args.group
            )

        if self.result.status == ExecutionStatus.OK:
            self.result.message = "No journal errors found"
        else:
            self.result.message = f"Found journal entries with priority <= {args.check_priority}"

        return self.result
