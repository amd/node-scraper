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

import json
import logging
from collections import defaultdict
from typing import Any, Optional

from .afid_events import build_afid_events_from_data
from .se_models import AfidEvent
from .serviceability_data import ServiceabilityDataModel


def load_afid_sag_data(path: Optional[str]) -> Optional[dict[str, Any]]:
    """Load AFID_SAG.json when path is set and readable."""
    if not path or not str(path).strip():
        return None
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def normalize_fru_name(name: str) -> str:
    """Normalize a FRU or action subject for comparison.

    Args:
        name: SAG fru or action_subject label.

    Returns:
        Uppercase label with hyphens replaced by underscores.
    """
    return str(name).strip().upper().replace("-", "_")


def _serviceable_catalog(sag: Optional[dict[str, Any]]) -> list[Any]:
    """Return the SAG list of serviceable groups.

    Args:
        sag: Loaded AFID SAG object.

    Returns:
        serviceable_fru when that list is present, otherwise serviceable_action_subject.
    """
    if not sag:
        return []
    for key in ("serviceable_fru", "serviceable_action_subject"):
        raw = sag.get(key)
        if isinstance(raw, list) and raw:
            return raw
    return []


def known_fru_names_from_sag(sag: Optional[dict[str, Any]]) -> list[str]:
    """Return normalized serviceable group names from the SAG catalog.

    Args:
        sag: Loaded AFID SAG object.

    Returns:
        Normalized fru or action_subject names declared in the SAG catalog.
    """
    names: list[str] = []
    for item in _serviceable_catalog(sag):
        if not isinstance(item, dict):
            continue
        for key in item:
            text = str(key).strip()
            if text:
                names.append(normalize_fru_name(text))
    return sorted(set(names))


def sag_fru_display_names(sag: Optional[dict[str, Any]]) -> list[str]:
    """Return serviceable group labels from the SAG catalog.

    Args:
        sag: Loaded AFID SAG object.

    Returns:
        Original fru or action_subject key text from the SAG catalog.
    """
    names: list[str] = []
    for item in _serviceable_catalog(sag):
        if not isinstance(item, dict):
            continue
        for key in item:
            text = str(key).strip()
            if text:
                names.append(text)
    return sorted(set(names))


def afid_entry_from_sag(afid: int, sag: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    """Return the afid map entry for one AFID when present."""
    if not sag:
        return None
    afid_map = sag.get("afid")
    if not isinstance(afid_map, dict):
        return None
    entry = afid_map.get(str(afid))
    return entry if isinstance(entry, dict) else None


def afid_fru_from_sag(afid: int, sag: Optional[dict[str, Any]]) -> Optional[str]:
    """Return the FRU or action subject for an AFID from the SAG afid table.

    Args:
        afid: AMD Fault ID.
        sag: Loaded AFID SAG object.

    Returns:
        afid.fru when set, otherwise afid.action_subject. None when neither is set.
    """
    entry = afid_entry_from_sag(afid, sag)
    if not entry:
        return None
    for key in ("fru", "action_subject"):
        value = entry.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def afid_summary_from_sag(afid: int, sag: Optional[dict[str, Any]]) -> Optional[str]:
    """Build a short human-readable AFID fault summary from SAG metadata."""
    entry = afid_entry_from_sag(afid, sag)
    if not entry:
        return None
    parts = [
        str(entry[key]).strip()
        for key in ("error_category", "error_type")
        if entry.get(key) is not None and str(entry[key]).strip()
    ]
    if parts:
        return " / ".join(parts)
    fallback = entry.get("service_action")
    if fallback is not None and str(fallback).strip():
        return str(fallback).strip()
    return None


def service_action_entry_from_sag(
    service_action_num: int,
    sag: Optional[dict[str, Any]],
) -> Optional[dict[str, Any]]:
    """Return the service_actions map entry for one service action number."""
    if not sag:
        return None
    actions = sag.get("service_actions")
    if not isinstance(actions, dict):
        return None
    entry = actions.get(str(service_action_num))
    return entry if isinstance(entry, dict) else None


def service_action_label_from_sag(
    service_action_num: int,
    sag: Optional[dict[str, Any]],
) -> Optional[str]:
    """Return the display title for a service action from the SAG."""
    entry = service_action_entry_from_sag(service_action_num, sag)
    if not entry:
        return None
    for key in ("title", "service_action"):
        value = entry.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def service_action_step_descriptions_from_sag(
    service_action_num: int,
    sag: Optional[dict[str, Any]],
) -> list[str]:
    """Return ordered step descriptions for a service action from the SAG."""
    entry = service_action_entry_from_sag(service_action_num, sag)
    if not entry:
        return []
    steps = entry.get("steps")
    if not isinstance(steps, list):
        return []
    out: list[str] = []
    for step in steps:
        if not isinstance(step, dict):
            continue
        desc = step.get("description")
        if desc is not None and str(desc).strip():
            out.append(str(desc).strip())
    return out


def group_afid_events_by_fru(
    events: list[AfidEvent],
    sag: Optional[dict[str, Any]],
) -> dict[str, list[AfidEvent]]:
    """Group parsed AFID events by SAG fru or action subject.

    Args:
        events: Parsed AFID events.
        sag: Loaded AFID SAG object.

    Returns:
        Events keyed by normalized fru or action subject. Missing labels use UNKNOWN_FRU.
    """
    grouped: dict[str, list[AfidEvent]] = defaultdict(list)
    for event in events:
        fru = afid_fru_from_sag(event.afid, sag) or "UNKNOWN_FRU"
        grouped[normalize_fru_name(fru)].append(event)
    return dict(grouped)


def format_collected_afid_fru_summary_lines(
    events: list[AfidEvent],
    sag: Optional[dict[str, Any]],
    *,
    rf_event_count: int = 0,
) -> list[str]:
    """Build log lines summarizing collected AFID events grouped by FRU."""
    if not events:
        return [f"No parseable AFID events from {rf_event_count} Redfish log member(s)."]
    lines = [
        f"Collected AFID events by FRU ({len(events)} parseable from "
        f"{rf_event_count} Redfish log member(s)):"
    ]
    grouped = group_afid_events_by_fru(events, sag)
    for fru in sorted(grouped.keys()):
        fru_events = grouped[fru]
        afid_counts: dict[int, int] = defaultdict(int)
        unit_counts: dict[str, int] = defaultdict(int)
        for event in fru_events:
            afid_counts[event.afid] += 1
            unit_counts[event.serviceable_unit] += 1
        afid_bits = ", ".join(f"{afid} x{count}" for afid, count in sorted(afid_counts.items()))
        unit_bits = ", ".join(f"{unit} x{count}" for unit, count in sorted(unit_counts.items()))
        lines.append(f"  {fru}: AFIDs [{afid_bits}]")
        lines.append(f"    units: {unit_bits}")
    return lines


def log_afid_fru_summary(
    logger: logging.Logger,
    parent: str,
    data: ServiceabilityDataModel,
    sag_path: Optional[str],
) -> None:
    """Log AFID counts grouped by FRU when AFID_SAG path is configured."""
    if not sag_path or not str(sag_path).strip():
        return
    sag = load_afid_sag_data(sag_path)
    events = build_afid_events_from_data(data)
    for line in format_collected_afid_fru_summary_lines(
        events,
        sag,
        rf_event_count=len(data.rf_events),
    ):
        logger.info("(%s) %s", parent, line)
