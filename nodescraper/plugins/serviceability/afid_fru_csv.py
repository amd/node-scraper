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

import csv
import logging
import os
from typing import Any, Optional

from .afid_events import build_afid_events_from_data
from .afid_sag_lookup import (
    afid_entry_from_sag,
    afid_fru_from_sag,
    afid_summary_from_sag,
    group_afid_events_by_fru,
    load_afid_sag_data,
    normalize_fru_name,
    sag_fru_display_names,
    service_action_label_from_sag,
)
from .se_models import HubTriageResult, ServiceabilityBlock
from .serviceability_data import DeviceInfo, ServiceabilityDataModel

AFID_FRU_SUMMARY_CSV = "afid_fru_summary.csv"

_SERIAL_KEYS: tuple[str, ...] = (
    "SerialNumber",
    "serial_number",
    "UbbSerial",
    "ubb_serial",
    "ProductSerialNumber",
    "product_serial_number",
)
_PART_KEYS: tuple[str, ...] = (
    "PartNumber",
    "part_number",
    "ProductPartNumber",
    "product_part_number",
    "BoardPartNumber",
    "board_part_number",
)
_NAME_KEYS: tuple[str, ...] = ("Name", "name", "Model", "model")
_VERSION_KEYS: tuple[str, ...] = ("Version", "version", "FirmwareVersion", "firmware_version")

AFID_FRU_CSV_COLUMNS: tuple[str, ...] = (
    "fru",
    "fru_text",
    "serial_number",
    "part_number",
    "unit_name",
    "unit_version",
    "afid",
    "fault",
    "fault_severity",
    "unit",
    "event_time",
    "priority",
    "service_action_num",
    "service_action_title",
    "sa_severity",
    "tier",
    "event_count",
)


def _empty_row() -> dict[str, str]:
    return {column: "" for column in AFID_FRU_CSV_COLUMNS}


def _text_value(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _first_nonempty(mapping: dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        text = _text_value(mapping.get(key))
        if text:
            return text
    return ""


def _identity_from_mapping(mapping: dict[str, Any]) -> dict[str, str]:
    return {
        "unit_name": _first_nonempty(mapping, _NAME_KEYS),
        "serial_number": _first_nonempty(mapping, _SERIAL_KEYS),
        "part_number": _first_nonempty(mapping, _PART_KEYS),
        "unit_version": _first_nonempty(mapping, _VERSION_KEYS),
    }


def _normalize_unit_key(unit: str) -> str:
    return str(unit).strip().upper().replace("-", "_")


def _assembly_by_unit(data: ServiceabilityDataModel) -> dict[str, DeviceInfo]:
    out: dict[str, DeviceInfo] = {}
    for key, info in (data.assembly_info or {}).items():
        norm = _normalize_unit_key(key)
        out[norm] = info
        parts = norm.split("_")
        if len(parts) >= 2:
            out["_".join(parts[-2:])] = info
    return out


def _match_assembly(unit: str, assembly_by_unit: dict[str, DeviceInfo]) -> Optional[DeviceInfo]:
    norm = _normalize_unit_key(unit)
    if norm in assembly_by_unit:
        return assembly_by_unit[norm]
    for key, info in assembly_by_unit.items():
        if norm.endswith(key) or key.endswith(norm):
            return info
    return None


def _identity_from_rf_member(member: dict[str, Any]) -> dict[str, str]:
    identity = _identity_from_mapping(member)
    oem = member.get("Oem")
    if not isinstance(oem, dict):
        return identity
    for fragment in oem.values():
        if not isinstance(fragment, dict):
            continue
        for field, value in _identity_from_mapping(fragment).items():
            if value and not identity[field]:
                identity[field] = value
        err_arr = fragment.get("ErrDataArr")
        if not isinstance(err_arr, list):
            continue
        for entry in err_arr:
            if not isinstance(entry, dict):
                continue
            for nested in (entry.get("MetaData"), entry.get("DecodedData")):
                if not isinstance(nested, dict):
                    continue
                for field, value in _identity_from_mapping(nested).items():
                    if value and not identity[field]:
                        identity[field] = value
    return identity


def _format_fru_text(identity: dict[str, str]) -> str:
    bits: list[str] = []
    if identity["unit_name"]:
        bits.append(identity["unit_name"])
    if identity["serial_number"]:
        bits.append(f"SN: {identity['serial_number']}")
    if identity["part_number"]:
        bits.append(f"PN: {identity['part_number']}")
    if identity["unit_version"]:
        bits.append(f"Ver: {identity['unit_version']}")
    return "; ".join(bits)


def _unit_identity(
    unit: str,
    *,
    assembly_by_unit: dict[str, DeviceInfo],
    rf_member: Optional[dict[str, Any]],
) -> dict[str, str]:
    identity = {
        "unit_name": "",
        "serial_number": "",
        "part_number": "",
        "unit_version": "",
    }
    device = _match_assembly(unit, assembly_by_unit)
    if device is not None:
        identity["unit_name"] = _text_value(device.name)
        identity["serial_number"] = _text_value(device.serial_number)
        identity["part_number"] = _text_value(device.part_number)
        identity["unit_version"] = _text_value(device.version)
    if rf_member is not None:
        from_rf = _identity_from_rf_member(rf_member)
        for field in identity:
            if not identity[field] and from_rf[field]:
                identity[field] = from_rf[field]
    return identity


def _rf_members_by_afid_unit(
    data: ServiceabilityDataModel,
) -> dict[tuple[int, str], dict[str, Any]]:
    from .afid_events import _afid_event_from_rf_member

    out: dict[tuple[int, str], dict[str, Any]] = {}
    for member in data.rf_events:
        if not isinstance(member, dict):
            continue
        parsed = _afid_event_from_rf_member(member)
        if parsed is None:
            continue
        key = (parsed.afid, parsed.serviceable_unit)
        if key not in out:
            out[key] = member
    return out


def _apply_unit_identity(row: dict[str, str], identity: dict[str, str]) -> None:
    row["fru_text"] = _format_fru_text(identity)
    row["serial_number"] = identity["serial_number"]
    row["part_number"] = identity["part_number"]
    row["unit_name"] = identity["unit_name"]
    row["unit_version"] = identity["unit_version"]


def _triage_lookup(
    block: Optional[ServiceabilityBlock],
) -> dict[tuple[int, str], HubTriageResult]:
    if block is None:
        return {}
    out: dict[tuple[int, str], HubTriageResult] = {}
    for row in block.hub_triage_results:
        out[(row.afid, row.location)] = row
    return out


def _row_from_event(
    *,
    fru: str,
    event,
    sag: Optional[dict[str, Any]],
    triage: Optional[HubTriageResult],
    unit_identity: dict[str, str],
) -> dict[str, str]:
    row = _empty_row()
    entry = afid_entry_from_sag(event.afid, sag)
    row["fru"] = fru
    _apply_unit_identity(row, unit_identity)
    row["afid"] = str(event.afid)
    row["fault"] = afid_summary_from_sag(event.afid, sag) or ""
    row["fault_severity"] = str(entry.get("error_severity") or "") if entry else ""
    row["unit"] = event.serviceable_unit
    row["event_time"] = event.time
    row["priority"] = str(entry.get("priority") or "") if entry else ""
    if triage is not None:
        row["service_action_num"] = str(triage.service_action_num)
        row["service_action_title"] = triage.service_action_title or ""
        row["sa_severity"] = str(triage.sa_severity or "")
        row["tier"] = triage.tier_label or ""
        row["event_count"] = str(triage.count)
        if triage.afid_summary:
            row["fault"] = triage.afid_summary
        if triage.priority is not None:
            row["priority"] = str(triage.priority)
    elif entry:
        san = entry.get("service_action_num")
        if san is not None:
            row["service_action_num"] = str(san)
            row["service_action_title"] = service_action_label_from_sag(int(san), sag) or str(
                entry.get("service_action") or ""
            )
        row["event_count"] = "1"
    else:
        row["event_count"] = "1"
    return row


def build_afid_fru_csv_rows(
    data: ServiceabilityDataModel,
    sag: Optional[dict[str, Any]],
) -> list[dict[str, str]]:
    """Build CSV rows for AFID events grouped by FRU, including empty rows for SAG FRUs with no events."""
    events = data.afid_events or build_afid_events_from_data(data)
    grouped = group_afid_events_by_fru(events, sag)
    triage_by_key = _triage_lookup(data.serviceability)
    assembly_by_unit = _assembly_by_unit(data)
    rf_by_key = _rf_members_by_afid_unit(data)
    rows: list[dict[str, str]] = []

    seen_fru: set[str] = set()
    for fru_key in sorted(grouped.keys()):
        seen_fru.add(fru_key)
        display_fru = afid_fru_from_sag(grouped[fru_key][0].afid, sag) or fru_key
        for event in sorted(
            grouped[fru_key],
            key=lambda item: (item.afid, item.serviceable_unit, item.time),
        ):
            triage = triage_by_key.get((event.afid, event.serviceable_unit))
            unit_identity = _unit_identity(
                event.serviceable_unit,
                assembly_by_unit=assembly_by_unit,
                rf_member=rf_by_key.get((event.afid, event.serviceable_unit)),
            )
            rows.append(
                _row_from_event(
                    fru=display_fru,
                    event=event,
                    sag=sag,
                    triage=triage,
                    unit_identity=unit_identity,
                )
            )

    for fru_name in sag_fru_display_names(sag):
        if normalize_fru_name(fru_name) in seen_fru:
            continue
        row = _empty_row()
        row["fru"] = fru_name
        rows.append(row)

    return rows


def write_afid_fru_summary_csv(
    data: ServiceabilityDataModel,
    log_path: str,
    *,
    logger: Optional[logging.Logger] = None,
    parent: Optional[str] = None,
) -> Optional[str]:
    """Write afid_fru_summary.csv under log_path when AFID_SAG path is configured."""
    sag_path = data.afid_sag_path
    if not sag_path or not str(sag_path).strip():
        return None
    sag = load_afid_sag_data(sag_path)
    if sag is None:
        return None

    rows = build_afid_fru_csv_rows(data, sag)
    os.makedirs(log_path, exist_ok=True)
    csv_path = os.path.join(log_path, AFID_FRU_SUMMARY_CSV)
    with open(csv_path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=AFID_FRU_CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    if logger is not None:
        label = parent or "serviceability"
        logger.info(
            "(%s) Wrote %s (%d row(s)) to %s",
            label,
            AFID_FRU_SUMMARY_CSV,
            len(rows),
            csv_path,
        )
    return csv_path
