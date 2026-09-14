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
from __future__ import annotations

from typing import Any, Optional

from nodescraper.connection.redfish import RF_MEMBERS

from .time_utils import TimeOperator, satisfies_time_check

_EVENT_TIMESTAMP_KEYS = ("Created", "EventTimestamp", "Timestamp")


def event_timestamp(event: dict[str, Any]) -> Optional[str]:
    """Return the first populated Redfish log-entry timestamp field."""
    for key in _EVENT_TIMESTAMP_KEYS:
        value = event.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def filter_event_log_members(
    members: list[Any],
    *,
    reference_time: Optional[str] = None,
    time_operator: Optional[TimeOperator] = None,
) -> list[Any]:
    """Filter log members by optional reference-time bounds."""
    if reference_time is None or time_operator is None:
        return list(members)
    filtered: list[Any] = []
    for member in members:
        if not isinstance(member, dict):
            filtered.append(member)
            continue
        timestamp = event_timestamp(member)
        if timestamp is None or satisfies_time_check(timestamp, reference_time, time_operator):
            filtered.append(member)
    return filtered


def _collect_members_from_responses(responses: dict[str, Any]) -> list[Any]:
    """Merge Members arrays from a URI-keyed redfish_responses map."""
    merged_members: list[Any] = []
    for body in responses.values():
        if not isinstance(body, dict):
            continue
        members = body.get(RF_MEMBERS)
        if isinstance(members, list):
            merged_members.extend(members)
    return merged_members


def _is_redfish_responses_map(payload: dict[str, Any]) -> bool:
    """Return True when payload looks like a collector redfish_responses.json dump."""
    if not payload:
        return False
    has_members = False
    for key, value in payload.items():
        if not isinstance(key, str) or not key.startswith("/"):
            return False
        if not isinstance(value, dict):
            return False
        if isinstance(value.get(RF_MEMBERS), list):
            has_members = True
    return has_members


def rf_events_from_json_payload(payload: Any) -> tuple[list[Any], dict[str, Any]]:
    """Normalize Redfish Entries JSON or a bare member list into rf_events + responses."""
    if isinstance(payload, list):
        return list(payload), {}

    if not isinstance(payload, dict):
        raise ValueError(
            "Serviceability data input must be a JSON object, Redfish Entries collection, "
            "redfish_responses.json dump, or a list of LogEntry members"
        )

    members = payload.get(RF_MEMBERS)
    if isinstance(members, list):
        responses: dict[str, Any] = {}
        odata_id = payload.get("@odata.id")
        if odata_id:
            responses[str(odata_id)] = payload
        return list(members), responses

    nested_responses = payload.get("responses")
    if isinstance(nested_responses, dict) and _is_redfish_responses_map(nested_responses):
        return _collect_members_from_responses(nested_responses), dict(nested_responses)

    if _is_redfish_responses_map(payload):
        return _collect_members_from_responses(payload), dict(payload)

    raise ValueError(
        "Serviceability data JSON must include rf_events, a Redfish Members array, "
        "or a redfish_responses.json URI map"
    )
