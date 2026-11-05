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
from typing import Optional

import pytest
from pydantic import ValidationError

from nodescraper.enums import EventPriority, ExecutionStatus
from nodescraper.plugins.ooband.redfish_event_log import (
    EventLogEntry,
    RedfishEventLogAnalyzer,
    RedfishEventLogAnalyzerArgs,
    RedfishEventLogDataModel,
)

ERRORS = "ResourceEvent.1.3.ResourceErrorsDetected"
THRESHOLD = "ResourceEvent.1.3.ResourceWarningThresholdExceeded"
STATUS_OK = "ResourceEvent.1.3.ResourceStatusChangedOK"


def _entry(
    entry_id: int,
    severity: Optional[str],
    message_id: Optional[str],
    day: int = 1,
    message: Optional[str] = None,
) -> EventLogEntry:
    return EventLogEntry(
        id=str(entry_id),
        created=f"2026-01-{day:02d}T00:00:00+00:00",
        severity=severity,
        message_id=message_id,
        message=message if message is not None else f"entry {entry_id}",
    )


def _analyze(entries: list[EventLogEntry], system_info, **args):
    data = RedfishEventLogDataModel(
        log_service_path="/redfish/v1/Systems/1/LogServices/EventLog",
        total_count=len(entries),
        entries=entries,
    )
    analyzer = RedfishEventLogAnalyzer(system_info=system_info)
    return analyzer.analyze_data(data, RedfishEventLogAnalyzerArgs(**args))


def test_empty_log_is_ok(system_info):
    result = _analyze([], system_info)

    assert result.status == ExecutionStatus.OK
    assert result.events == []


def test_only_ok_entries_are_ok(system_info):
    result = _analyze([_entry(1, "OK", STATUS_OK)], system_info)

    assert result.status == ExecutionStatus.OK
    assert result.events == []


def test_critical_and_warning_map_to_error_and_warning(system_info):
    entries = [
        _entry(3, "Critical", ERRORS, day=3),
        _entry(2, "Warning", THRESHOLD, day=2),
        _entry(1, "OK", STATUS_OK, day=1),
    ]

    result = _analyze(entries, system_info)

    assert result.status == ExecutionStatus.ERROR
    priorities = {e.data["message_id"]: e.priority for e in result.events}
    assert priorities == {ERRORS: EventPriority.ERROR, THRESHOLD: EventPriority.WARNING}
    assert "1 critical, 1 warning" in result.message


def test_warning_only_is_warning(system_info):
    result = _analyze([_entry(1, "Warning", THRESHOLD)], system_info)

    assert result.status == ExecutionStatus.WARNING


def test_repeats_collapse_with_count_and_newest_message(system_info):
    entries = [
        _entry(3, "Critical", ERRORS, day=3, message="newest"),
        _entry(2, "Critical", ERRORS, day=2, message="middle"),
        _entry(1, "Critical", ERRORS, day=1, message="oldest"),
    ]

    result = _analyze(entries, system_info)

    assert len(result.events) == 1
    event = result.events[0]
    assert "(x3)" in event.description
    assert event.description.endswith(": newest")
    assert event.data["count"] == 3
    assert event.data["ids"] == ["3", "2", "1"]
    assert event.data["oldest_created"].startswith("2026-01-01")


def test_severity_match_is_case_insensitive(system_info):
    result = _analyze([_entry(1, "CRITICAL", ERRORS)], system_info)

    assert result.status == ExecutionStatus.ERROR


def test_entries_without_message_id_group_by_message(system_info):
    entries = [
        _entry(2, "Warning", None, message="fan degraded"),
        _entry(1, "Warning", None, message="fan degraded"),
        _entry(3, "Warning", None, message="psu degraded"),
    ]

    result = _analyze(entries, system_info)

    assert sorted(e.data["count"] for e in result.events) == [1, 2]
    assert all("LogEntry" in e.description for e in result.events)


def test_since_skips_older_entries_but_keeps_undated(system_info):
    entries = [
        _entry(2, "Critical", ERRORS, day=5),
        _entry(1, "Critical", THRESHOLD, day=1),
        EventLogEntry(id="9", created="unknown", severity="Warning", message_id=THRESHOLD),
    ]

    result = _analyze(entries, system_info, since="2026-01-03T00:00:00")

    assert {(e.data["message_id"], e.data["count"]) for e in result.events} == {
        (ERRORS, 1),
        (THRESHOLD, 1),
    }
    assert "in 2 of 3 entries" in result.message


def test_message_id_include_and_exclude(system_info):
    entries = [_entry(2, "Critical", ERRORS), _entry(1, "Warning", THRESHOLD)]

    included = _analyze(entries, system_info, message_id_include=[r"ResourceErrors"])
    excluded = _analyze(entries, system_info, message_id_exclude=[r"Threshold"])

    assert [e.data["message_id"] for e in included.events] == [ERRORS]
    assert [e.data["message_id"] for e in excluded.events] == [ERRORS]


def test_invalid_regex_is_rejected():
    with pytest.raises(ValidationError):
        RedfishEventLogAnalyzerArgs(message_id_exclude=["("])
