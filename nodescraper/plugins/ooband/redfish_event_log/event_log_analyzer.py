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
import re
from typing import Optional

from nodescraper.enums import EventCategory, EventPriority, ExecutionStatus
from nodescraper.interfaces import DataAnalyzer
from nodescraper.models import TaskResult

from .analyzer_args import RedfishEventLogAnalyzerArgs
from .event_log_data import EventLogEntry, RedfishEventLogDataModel, parse_created

SEVERITY_PRIORITY: dict[str, EventPriority] = {
    "critical": EventPriority.ERROR,
    "warning": EventPriority.WARNING,
}
MAX_IDS_PER_EVENT = 20


def _selected(entry: EventLogEntry, args: RedfishEventLogAnalyzerArgs) -> bool:
    if args.since is not None:
        created = parse_created(entry.created)
        if created is not None and created < args.since:
            return False
    message_id = entry.message_id or ""
    if args.message_id_include is not None and not any(
        re.search(p, message_id) for p in args.message_id_include
    ):
        return False
    return not any(re.search(p, message_id) for p in args.message_id_exclude)


class RedfishEventLogAnalyzer(DataAnalyzer[RedfishEventLogDataModel, RedfishEventLogAnalyzerArgs]):
    """Reports Critical and Warning LogService entries as events."""

    DATA_MODEL = RedfishEventLogDataModel

    DOCUMENTATION_ANALYSIS_ITEMS: tuple[str, ...] = (
        "Critical entries are reported as ERROR events and Warning entries as WARNING events; "
        "OK and other severities are ignored.",
        "Entries with the same Severity and MessageId are reported once with a count and the newest message.",
        "analysis_args.since, message_id_include and message_id_exclude limit which entries are analyzed.",
    )

    def analyze_data(
        self,
        data: RedfishEventLogDataModel,
        args: Optional[RedfishEventLogAnalyzerArgs] = None,
    ) -> TaskResult:
        """Report Critical and Warning entries, collapsed by Severity and MessageId."""
        if args is None:
            args = RedfishEventLogAnalyzerArgs()

        selected = [e for e in data.entries if _selected(e, args)]
        groups: dict[tuple[str, str], list[EventLogEntry]] = {}
        for entry in selected:
            severity = (entry.severity or "").lower()
            if severity in SEVERITY_PRIORITY:
                key = (severity, entry.message_id or entry.message or "")
                groups.setdefault(key, []).append(entry)

        counts = {severity: 0 for severity in SEVERITY_PRIORITY}
        for (severity, _), group in groups.items():
            counts[severity] += len(group)
            newest = group[0]
            label = newest.message_id or "LogEntry"
            repeat = f" (x{len(group)})" if len(group) > 1 else ""
            detail = f": {newest.message}" if newest.message else ""
            self._log_event(
                category=EventCategory.PLATFORM,
                description=f"{newest.severity} {label}{repeat}{detail}",
                data={
                    "log_service_path": data.log_service_path,
                    "severity": newest.severity,
                    "message_id": newest.message_id,
                    "count": len(group),
                    "newest_created": newest.created,
                    "oldest_created": group[-1].created,
                    "message_args": newest.message_args,
                    "ids": [e.id for e in group[:MAX_IDS_PER_EVENT]],
                },
                priority=SEVERITY_PRIORITY[severity],
                console_log=True,
            )

        self.result.message = (
            f"EventLog: {counts['critical']} critical, {counts['warning']} warning "
            f"in {len(selected)} of {len(data.entries)} entries"
        )
        if counts["critical"]:
            self.result.status = ExecutionStatus.ERROR
        elif counts["warning"]:
            self.result.status = ExecutionStatus.WARNING
        else:
            self.result.status = ExecutionStatus.OK
        return self.result
