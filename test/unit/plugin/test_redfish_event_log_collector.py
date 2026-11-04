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
from datetime import datetime, timezone
from typing import Any, Optional
from unittest.mock import MagicMock, patch

import pytest

from nodescraper.connection.redfish import RedfishGetResult
from nodescraper.connection.redfish.redfish_clear_log import ClearLogResult
from nodescraper.enums import ExecutionStatus, SystemInteractionLevel
from nodescraper.plugins.ooband.redfish_event_log import (
    EventLogEntry,
    RedfishEventLogCollector,
    RedfishEventLogCollectorArgs,
)
from nodescraper.plugins.ooband.redfish_event_log.event_log_data import parse_created

SERVICE = "/redfish/v1/Systems/1/LogServices/EventLog"
ENTRIES = f"{SERVICE}/Entries"


def _entry(entry_id: int, day: int, severity: str = "OK") -> dict[str, Any]:
    return {
        "@odata.id": f"{ENTRIES}/{entry_id}",
        "Id": str(entry_id),
        "Created": f"2026-01-{day:02d}T00:00:00+00:00",
        "Severity": severity,
        "MessageId": "ResourceEvent.1.3.ResourceStatusChangedOK",
        "Message": f"entry {entry_id}",
    }


def _page(members: list, count: Optional[int] = None, next_link: Optional[str] = None) -> dict:
    body: dict[str, Any] = {"Members": members}
    if count is not None:
        body["Members@odata.count"] = count
    if next_link is not None:
        body["Members@odata.nextLink"] = next_link
    return body


def _connection(pages: dict[str, Optional[dict]]) -> MagicMock:
    conn = MagicMock()

    def run_get(path: str) -> RedfishGetResult:
        body = pages.get(str(path))
        if body is None:
            return RedfishGetResult(
                path=str(path), success=False, error="not found", status_code=404
            )
        return RedfishGetResult(path=str(path), success=True, data=body, status_code=200)

    conn.run_get.side_effect = run_get
    return conn


def _collect(pages, system_info, level=SystemInteractionLevel.INTERACTIVE, **args):
    conn = _connection(pages)
    collector = RedfishEventLogCollector(
        system_info=system_info, connection=conn, system_interaction_level=level
    )
    result, data = collector.collect_data(
        RedfishEventLogCollectorArgs(log_service_path=SERVICE, **args)
    )
    requested = [str(c.args[0]) for c in conn.run_get.call_args_list]
    return result, data, requested


def test_pages_with_skip_and_ignores_static_next_link(system_info):
    static_next = f"{ENTRIES}?$skip=2"
    pages = {
        ENTRIES: _page([_entry(1, 1), _entry(2, 3)], count=3, next_link=static_next),
        f"{ENTRIES}?$skip=2": _page([_entry(3, 2)], count=3, next_link=static_next),
    }

    result, data, requested = _collect(pages, system_info)

    assert result.status == ExecutionStatus.OK
    assert requested == [ENTRIES, f"{ENTRIES}?$skip=2"]
    assert [e.id for e in data.entries] == ["2", "3", "1"]
    assert data.total_count == 3
    assert len(result.artifacts) == 2


def test_single_page_without_count_or_next_link(system_info):
    result, data, requested = _collect({ENTRIES: _page([_entry(1, 1)])}, system_info)

    assert result.status == ExecutionStatus.OK
    assert requested == [ENTRIES]
    assert data.total_count == 1


def test_empty_log(system_info):
    result, data, _ = _collect({ENTRIES: _page([], count=0)}, system_info)

    assert result.status == ExecutionStatus.OK
    assert data.entries == []


def test_service_ignoring_skip_stops_with_warning(system_info):
    same_page = _page([_entry(1, 1), _entry(2, 2)], count=5)
    pages = {ENTRIES: same_page, f"{ENTRIES}?$skip=2": same_page}

    result, data, requested = _collect(pages, system_info)

    assert result.status == ExecutionStatus.WARNING
    assert requested == [ENTRIES, f"{ENTRIES}?$skip=2"]
    assert len(data.entries) == 2
    assert any("no new entries" in e.description for e in result.events)


def test_first_page_failure_returns_no_data(system_info):
    result, data, _ = _collect({}, system_info)

    assert result.status == ExecutionStatus.EXECUTION_FAILURE
    assert data is None


def test_later_page_failure_keeps_partial_data(system_info):
    pages = {ENTRIES: _page([_entry(1, 1)], count=2)}

    result, data, _ = _collect(pages, system_info)

    assert result.status == ExecutionStatus.WARNING
    assert [e.id for e in data.entries] == ["1"]
    assert data.total_count == 2


def test_max_entries_keeps_newest(system_info):
    pages = {ENTRIES: _page([_entry(1, 1), _entry(2, 3), _entry(3, 2)], count=3)}

    _, data, _ = _collect(pages, system_info, max_entries=2)

    assert [e.id for e in data.entries] == ["2", "3"]
    assert data.total_count == 3


def test_max_pages_cap(system_info):
    pages = {
        ENTRIES: _page([_entry(1, 1)], count=3),
        f"{ENTRIES}?$skip=1": _page([_entry(2, 2)], count=3),
    }

    result, data, requested = _collect(pages, system_info, max_pages=2)

    assert result.status == ExecutionStatus.WARNING
    assert len(requested) == 2
    assert len(data.entries) == 2


@patch("nodescraper.plugins.ooband.redfish_event_log.event_log_collector.clear_redfish_logs")
def test_clear_log_when_interactive(mock_clear, system_info):
    target = f"{SERVICE}/Actions/LogService.ClearLog"
    pages = {
        ENTRIES: _page([_entry(1, 1)], count=1),
        SERVICE: {"Actions": {"#LogService.ClearLog": {"target": target}}},
    }
    mock_clear.return_value = [ClearLogResult(path=target, success=True)]

    result, _, _ = _collect(pages, system_info, clear_logs_after_collection=True)

    mock_clear.assert_called_once()
    assert mock_clear.call_args.args[1][0].path == target
    assert "cleared log store" in result.message


@patch("nodescraper.plugins.ooband.redfish_event_log.event_log_collector.clear_redfish_logs")
def test_clear_log_skipped_when_passive(mock_clear, system_info):
    pages = {ENTRIES: _page([_entry(1, 1)], count=1)}

    _collect(
        pages,
        system_info,
        level=SystemInteractionLevel.PASSIVE,
        clear_logs_after_collection=True,
    )

    mock_clear.assert_not_called()


def test_entry_from_redfish_tolerates_missing_and_scalar_fields():
    entry = EventLogEntry.from_redfish({"Id": 7, "MessageArgs": "SN0001"})

    assert entry.id == "7"
    assert entry.message_args == ["SN0001"]
    assert entry.severity is None


@pytest.mark.parametrize(
    "value, expected",
    [
        ("2026-01-01T00:00:00Z", datetime(2026, 1, 1, tzinfo=timezone.utc)),
        ("2026-01-01T00:00:00", datetime(2026, 1, 1, tzinfo=timezone.utc)),
        ("not a time", None),
        (None, None),
    ],
)
def test_parse_created(value, expected):
    assert parse_created(value) == expected
