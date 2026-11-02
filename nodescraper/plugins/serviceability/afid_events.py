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
    """Build hub input events from collected Redfish and CPER fields."""
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


def rf_member_is_afid_parseable(member: Any) -> bool:
    """Return True when a Redfish log member has AFID, serviceable unit, and timestamp."""
    return _afid_event_from_rf_member(member) is not None


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


def _oem_mappings(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Return Oem objects on a log entry, including one nested under CPER.

    Args:
        payload: Redfish log member or switch event.

    Returns:
        Oem mappings that may contain AMDFieldIdentifiers.
    """
    found: list[dict[str, Any]] = []
    oem = payload.get("Oem")
    if isinstance(oem, dict):
        found.append(oem)
    cper = payload.get("CPER")
    if isinstance(cper, dict):
        nested = cper.get("Oem")
        if isinstance(nested, dict):
            found.append(nested)
    return found


def _extract_afid(payload: dict[str, Any]) -> Optional[int]:
    for key in _AFID_KEYS:
        if key in payload and payload[key] is not None:
            return int(payload[key])
    for oem in _oem_mappings(payload):
        for vendor_payload in oem.values():
            found = _extract_afid_from_oem_fragment(vendor_payload)
            if found is not None:
                return found
    return None


def _afid_from_field_identifiers(identifiers: Any) -> Optional[int]:
    if not isinstance(identifiers, list):
        return None
    for item in identifiers:
        if not isinstance(item, dict):
            continue
        for key in _AFID_KEYS:
            if key in item and item[key] is not None:
                return int(item[key])
    return None


def _extract_afid_from_oem_fragment(vendor_payload: Any) -> Optional[int]:
    """Resolve AFID from one ``Oem`` property value (dict or list of dicts, e.g. ``AMDFieldIdentifiers``)."""
    if isinstance(vendor_payload, dict):
        for key in _AFID_KEYS:
            if key in vendor_payload and vendor_payload[key] is not None:
                return int(vendor_payload[key])
        found = _afid_from_field_identifiers(vendor_payload.get("AMDFieldIdentifiers"))
        if found is not None:
            return found
    elif isinstance(vendor_payload, list):
        found = _afid_from_field_identifiers(vendor_payload)
        if found is not None:
            return found
    return None


def _origin_dict_to_unit(value: Any) -> Optional[str]:
    if not isinstance(value, dict):
        return None
    odata_id = value.get("@odata.id") or value.get("odata.id")
    if odata_id:
        return _unit_from_odata_id(str(odata_id))
    return None


def _unit_odata_id(unit: Any) -> Optional[str]:
    if not isinstance(unit, dict):
        return None
    for key in ("@odata.id", "odata.id"):
        value = unit.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


def usable_serviceable_units(units: Any) -> list[Any]:
    """Return ServiceableUnits entries that carry an @odata.id or odata.id string.

    Args:
        units: ServiceableUnits value from an AFID identifier entry.

    Returns:
        Unit objects that name a location. Empty when none qualify.
    """
    if not isinstance(units, list):
        return []
    return [unit for unit in units if _unit_odata_id(unit) is not None]


def promote_serviceable_unit_odata_ids(member: dict[str, Any]) -> dict[str, Any]:
    """Copy odata.id onto @odata.id so the hub can read the location.

    Args:
        member: Redfish log member.

    Returns:
        The same member, or a copy when a ServiceableUnits entry needed @odata.id.
    """
    oem = member.get("Oem")
    if not isinstance(oem, dict):
        return member
    amd = oem.get("AMD")
    if not isinstance(amd, dict):
        return member
    identifiers = amd.get("AMDFieldIdentifiers")
    if not isinstance(identifiers, list):
        return member
    new_identifiers: list[Any] = []
    changed = False
    for entry in identifiers:
        if not isinstance(entry, dict) or not isinstance(entry.get("ServiceableUnits"), list):
            new_identifiers.append(entry)
            continue
        new_units: list[Any] = []
        entry_changed = False
        for unit in entry["ServiceableUnits"]:
            if (
                isinstance(unit, dict)
                and not isinstance(unit.get("@odata.id"), str)
                and isinstance(unit.get("odata.id"), str)
                and unit["odata.id"].strip()
            ):
                copied = dict(unit)
                copied["@odata.id"] = unit["odata.id"]
                new_units.append(copied)
                entry_changed = True
            else:
                new_units.append(unit)
        if entry_changed:
            changed = True
            new_identifiers.append({**entry, "ServiceableUnits": new_units})
        else:
            new_identifiers.append(entry)
    if not changed:
        return member
    return {
        **member,
        "Oem": {**oem, "AMD": {**amd, "AMDFieldIdentifiers": new_identifiers}},
    }


def amd_field_identifiers_with_units(
    oem: Any,
) -> Optional[tuple[list[dict[str, Any]], list[Any]]]:
    """Split Oem.AMD.AMDFieldIdentifiers by whether ServiceableUnits is usable.

    Args:
        oem: Redfish Oem object from a log member.

    Returns:
        (usable entries, unusable entries) when Oem.AMD.AMDFieldIdentifiers is a list.
        None when that shape is absent so another source shape can be tried.
    """
    if not isinstance(oem, dict):
        return None
    amd = oem.get("AMD")
    if not isinstance(amd, dict):
        return None
    identifiers = amd.get("AMDFieldIdentifiers")
    if not isinstance(identifiers, list):
        return None
    usable: list[dict[str, Any]] = []
    unusable: list[Any] = []
    for entry in identifiers:
        units = entry.get("ServiceableUnits") if isinstance(entry, dict) else None
        if isinstance(entry, dict) and usable_serviceable_units(units):
            usable.append(entry)
        else:
            unusable.append(entry)
    return usable, unusable


_LOCATION_EXTRACTORS = (amd_field_identifiers_with_units,)


def split_afid_location_entries(
    oem: Any,
) -> Optional[tuple[list[dict[str, Any]], list[Any]]]:
    """Return usable and unusable AFID entries for the first matching source shape.

    Args:
        oem: Redfish Oem object from a log member.

    Returns:
        (usable, unusable) for a recognized shape, or None when no shape applies.
    """
    for extractor in _LOCATION_EXTRACTORS:
        split = extractor(oem)
        if split is not None:
            return split
    return None


def _first_unit_from_identifiers(identifiers: Any) -> Optional[str]:
    if not isinstance(identifiers, list):
        return None
    for item in identifiers:
        if not isinstance(item, dict):
            continue
        units = item.get("ServiceableUnits") or item.get("serviceable_units")
        for unit in usable_serviceable_units(units):
            name = _origin_dict_to_unit(unit)
            if name:
                return name
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

    links = payload.get("Links") or payload.get("links")
    if isinstance(links, dict):
        ooc = (
            links.get("OriginOfCondition")
            or links.get("originOfCondition")
            or links.get("OriginofCondition")
        )
        unit = _origin_dict_to_unit(ooc)
        if unit:
            return unit

    for oem in _oem_mappings(payload):
        for vendor_name, vendor_payload in oem.items():
            if isinstance(vendor_payload, dict):
                unit = vendor_payload.get("serviceable_unit") or vendor_payload.get(
                    "ServiceableUnit"
                )
                if unit is not None and str(unit).strip():
                    return str(unit).strip()
                if vendor_name != "AMD":
                    unit = _first_unit_from_identifiers(vendor_payload.get("AMDFieldIdentifiers"))
                    if unit:
                        return unit
            else:
                unit = _first_unit_from_identifiers(vendor_payload)
                if unit:
                    return unit
        split = amd_field_identifiers_with_units(oem)
        if split is not None:
            unit = _first_unit_from_identifiers(split[0])
            if unit:
                return unit
    return _switch_serviceable_unit(payload)


def _switch_serviceable_unit(payload: dict[str, Any]) -> Optional[str]:
    """Return the component name carried by one switch event.

    Args:
        payload: Switch event object.

    Returns:
        object-ref name, unit id, or node name, or None when this is not a switch event.
    """
    if payload.get("kind") != "Event":
        return None
    object_ref = payload.get("object-ref")
    if not isinstance(object_ref, dict):
        object_ref = payload.get("object_ref")
    if isinstance(object_ref, dict):
        name = object_ref.get("name")
        if isinstance(name, str) and name.strip():
            return name.strip()
    source = payload.get("source")
    if not isinstance(source, dict):
        return None
    for key in ("unit-id", "node-name"):
        value = source.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _extract_timestamp(payload: dict[str, Any]) -> Optional[str]:
    for key in _EVENT_TIMESTAMP_KEYS:
        text = _timestamp_text(payload.get(key))
        if text:
            return text
    meta = payload.get("meta")
    if isinstance(meta, dict):
        for key in ("creation-time", "mod-time"):
            text = _timestamp_text(meta.get(key))
            if text:
                return text
    return None


def _timestamp_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).replace("\x00", "").strip()


def _unit_from_odata_id(odata_id: str) -> str:
    segment = odata_id.rstrip("/").split("/")[-1]
    return segment or odata_id
