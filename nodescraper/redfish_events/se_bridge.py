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
"""Bridge RedfishEvent objects into serviceability plugin rf_events shape."""
from __future__ import annotations

from typing import Any

from .models import RedfishEvent


def redfish_event_to_log_member(event: RedfishEvent) -> dict[str, Any]:
    """Return a dict suitable for ServiceabilityDataModel.rf_events entries."""
    if event.raw:
        return dict(event.raw)
    member: dict[str, Any] = {
        "Message": event.message,
        "Severity": event.severity,
        "EventType": event.event_type,
    }
    if event.message_id:
        member["MessageId"] = event.message_id
    if event.origin_of_condition:
        member["OriginOfCondition"] = {"@odata.id": event.origin_of_condition}
    if event.event_timestamp:
        member["EventTimestamp"] = event.event_timestamp.isoformat()
        member["Created"] = member["EventTimestamp"]
    if event.source_id:
        member["@odata.id"] = event.source_id
        member["Id"] = event.source_id.rstrip("/").split("/")[-1]
    return member


def redfish_events_to_log_members(events: list[RedfishEvent]) -> list[dict[str, Any]]:
    """Convert a batch of ingest events for on-demand serviceability analysis."""
    return [redfish_event_to_log_member(event) for event in events]
