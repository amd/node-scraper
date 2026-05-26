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

from .se_models import AfidEvent
from .serviceability_data import ServiceabilityDataModel
from .time_utils import normalize_se_timestamp

_EVENT_TIMESTAMP_KEYS = ("Created", "EventTimestamp", "Timestamp")
_AFID_KEYS = ("Afid", "AFID", "afid")


def build_afid_events_from_data(data: ServiceabilityDataModel) -> list[AfidEvent]:
    """Build SE input events from collected Redfish and CPER fields."""
    events: list[AfidEvent] = []
    seen: set[tuple[int, str, str]] = set()

    for rf_event in data.rf_events:
        parsed = _afid_event_from_rf_member(rf_event)
        if parsed is None:
            continue
        key = (parsed.afid, parsed.serviceable_unit, parsed.time)
        if key in seen:
            continue
        seen.add(key)
        events.append(parsed)

    for unit, payload in data.cper_data.items():
        parsed = _afid_event_from_cper_slot(str(unit), payload)
        if parsed is None:
            continue
        key = (parsed.afid, parsed.serviceable_unit, parsed.time)
        if key in seen:
            continue
        seen.add(key)
        events.append(parsed)

    return events


def _afid_event_from_rf_member(member: Any) -> Optional[AfidEvent]:
    if not isinstance(member, dict):
        return None
    afid = _extract_afid(member)
    unit = _extract_serviceable_unit(member)
    timestamp = _extract_timestamp(member)
    if afid is None or unit is None or timestamp is None:
        return None
    return AfidEvent(
        afid=afid,
        serviceable_unit=unit,
        time=normalize_se_timestamp(timestamp),
    )


def _afid_event_from_cper_slot(unit: str, payload: Any) -> Optional[AfidEvent]:
    if not isinstance(payload, dict):
        return None
    afid = _extract_afid(payload)
    timestamp = _extract_timestamp(payload)
    unit_name = str(payload.get("serviceable_unit") or unit).strip()
    if afid is None or not unit_name or timestamp is None:
        return None
    return AfidEvent(
        afid=afid,
        serviceable_unit=unit_name,
        time=normalize_se_timestamp(timestamp),
    )


def _extract_afid(payload: dict[str, Any]) -> Optional[int]:
    for key in _AFID_KEYS:
        if key in payload and payload[key] is not None:
            return int(payload[key])
    oem = payload.get("Oem")
    if isinstance(oem, dict):
        for vendor_payload in oem.values():
            if isinstance(vendor_payload, dict):
                for key in _AFID_KEYS:
                    if key in vendor_payload and vendor_payload[key] is not None:
                        return int(vendor_payload[key])
    return None


def _extract_serviceable_unit(payload: dict[str, Any]) -> Optional[str]:
    for key in ("serviceable_unit", "ServiceableUnit", "OriginOfCondition", "Device"):
        value = payload.get(key)
        if value is None:
            continue
        if isinstance(value, dict):
            odata_id = value.get("@odata.id") or value.get("odata.id")
            if odata_id:
                return _unit_from_odata_id(str(odata_id))
        text = str(value).strip()
        if text:
            return _unit_from_odata_id(text) if "/" in text else text
    oem = payload.get("Oem")
    if isinstance(oem, dict):
        for vendor_payload in oem.values():
            if isinstance(vendor_payload, dict):
                unit = vendor_payload.get("serviceable_unit") or vendor_payload.get(
                    "ServiceableUnit"
                )
                if unit is not None and str(unit).strip():
                    return str(unit).strip()
    return None


def _extract_timestamp(payload: dict[str, Any]) -> Optional[str]:
    for key in _EVENT_TIMESTAMP_KEYS:
        value = payload.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def _unit_from_odata_id(odata_id: str) -> str:
    segment = odata_id.rstrip("/").split("/")[-1]
    return segment or odata_id
