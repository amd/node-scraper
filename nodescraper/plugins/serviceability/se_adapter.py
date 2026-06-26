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
"""Map serviceability plugin models to/from Python service hub results."""
from __future__ import annotations

import json
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from .se_models import AfidEvent, ServiceabilityBlock, ServiceabilitySolution

# Hub payload keys commonly holding a one-line human summary (not raw OEM metadata).
_SUMMARY_VALUE_KEYS: Tuple[str, ...] = (
    "short_service",
    "short_service_info",
    "summary",
    "message",
    "title",
    "recommendation",
    "solution",
    "service_recommendation",
    "action",
)
_UNIT_LABEL_KEYS: Tuple[str, ...] = (
    "oem",
    "OEM",
    "unit",
    "serviceable_unit",
    "designation",
    "chassis",
    "device",
)


def _hub_version_display(version_info: Any) -> Optional[str]:
    """Pick a single hub version string from common hub result version dict layouts."""
    if not isinstance(version_info, dict) or not version_info:
        return None
    primary = (
        version_info.get("isa_version")
        or version_info.get("version")
        or version_info.get("engine_version")
        or version_info.get("VERSION")
    )
    if primary is None:
        return None
    text = str(primary).strip()
    if not text:
        return None
    bd = version_info.get("build_date")
    if bd and str(bd).strip():
        return f"{text} (build {str(bd).strip()})"
    return text


def _afid_sag_file_version_display(metadata: Any) -> Optional[str]:
    """Build AFID_SAG file identity string (pid, revision, variant) from hub metadata."""
    if not isinstance(metadata, dict) or not metadata:
        return None
    pid = metadata.get("sag_pid") or metadata.get("pid")
    rev = metadata.get("revision")
    variant = metadata.get("variant")
    parts: list[str] = []
    if pid and str(pid).strip():
        parts.append(f"PID {str(pid).strip()}")
    if rev and str(rev).strip():
        parts.append(f"revision {str(rev).strip()}")
    if variant and str(variant).strip():
        parts.append(f"variant {str(variant).strip()}")
    if not parts:
        return None
    return ", ".join(parts)


def _human_summary_line_from_hub_value(value: Any) -> Optional[str]:
    """Pick a single human-readable line from a hub fragment (string, number, or dict)."""
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        return text or None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value).strip() or None
    if isinstance(value, dict):
        for key in _SUMMARY_VALUE_KEYS:
            if key not in value:
                continue
            got = _human_summary_line_from_hub_value(value[key])
            if got:
                return got
        for key in ("service_action", "ServiceAction"):
            if key not in value:
                continue
            raw = value[key]
            if isinstance(raw, dict):
                inner = (
                    raw.get("title")
                    or raw.get("text")
                    or raw.get("name")
                    or raw.get("service_action")
                )
                if isinstance(inner, str) and inner.strip():
                    return inner.strip()
                got = _human_summary_line_from_hub_value(raw)
                if got:
                    return got
            else:
                s = str(raw).strip()
                if s:
                    return s
        for alt in ("text", "name", "description", "details"):
            if isinstance(value.get(alt), str) and str(value[alt]).strip():
                return str(value[alt]).strip()
        return None
    text = str(value).strip()
    return text or None


def _unit_label_from_short_service_item(item: dict[str, Any]) -> str:
    for key in _UNIT_LABEL_KEYS:
        raw = item.get(key)
        if raw is not None and str(raw).strip():
            return str(raw).strip()
    return ""


def _maybe_unwrap_outer_unit_map(d: dict[str, Any]) -> dict[str, Any]:
    """If the hub wraps {wrapper: {unit: {...}}}, return the inner unit map."""
    if len(d) != 1:
        return d
    _, inner = next(iter(d.items()))
    if isinstance(inner, dict) and inner and all(isinstance(v, dict) for v in inner.values()):
        return inner
    return d


def _merged_short_service_lines_from_unit_messages(entries: List[Tuple[str, str]]) -> List[str]:
    """Group (unit, message) rows by message; merge units when the message is identical."""
    by_message: dict[str, list[str]] = defaultdict(list)
    for unit, msg in entries:
        if not msg:
            continue
        by_message[msg].append(unit or "")

    lines: list[str] = []
    for msg in sorted(by_message.keys(), key=lambda m: (-len(by_message[m]), m.lower())):
        units = sorted({u for u in by_message[msg] if u})
        if len(units) <= 1:
            u = units[0] if units else ""
            lines.append(f"{msg} ({u})" if u else msg)
        else:
            lines.append(f"{msg} — OEMs/units: {', '.join(units)}")
    return lines


def _format_short_service_info_for_block(raw: Any) -> Optional[str]:
    """Turn hub ``short_service_info`` into multiline log/LLM text (no JSON dump of unit maps)."""
    if raw is None:
        return None
    if isinstance(raw, str):
        text = raw.strip()
        return text or None
    if isinstance(raw, (list, tuple)):
        if raw and all(isinstance(x, dict) for x in raw):
            entries: list[tuple[str, str]] = []
            for item in raw:
                assert isinstance(item, dict)
                unit = _unit_label_from_short_service_item(item)
                msg = _human_summary_line_from_hub_value(
                    item
                ) or _human_summary_line_from_hub_value(item.get("short_service_info"))
                if msg:
                    entries.append((unit, msg))
            lines = _merged_short_service_lines_from_unit_messages(entries)
            out = "\n".join(lines).strip()
            return out or None
        parts = [str(x).strip() for x in raw if x is not None and str(x).strip()]
        return "\n".join(parts) if parts else None
    if isinstance(raw, dict):
        d = _maybe_unwrap_outer_unit_map(raw)
        if d and all(isinstance(v, dict) for v in d.values()):
            entries = []
            for unit_key, inner in d.items():
                msg = _human_summary_line_from_hub_value(inner)
                if msg:
                    entries.append((str(unit_key).strip(), msg))
            lines = _merged_short_service_lines_from_unit_messages(entries)
            out = "\n".join(lines).strip()
            if out:
                return out
        flat_lines: list[str] = []
        for key in sorted(d.keys(), key=lambda x: str(x).lower()):
            val = d[key]
            if isinstance(val, dict):
                msg = _human_summary_line_from_hub_value(val)
                if msg:
                    flat_lines.append(f"{key}: {msg}")
            elif val is not None and str(val).strip():
                flat_lines.append(f"{key}: {str(val).strip()}")
        if flat_lines:
            return "\n".join(flat_lines)
        try:
            compact = json.dumps(d, sort_keys=True)
        except TypeError:
            compact = str(d)
        compact = compact.strip()
        return compact or None
    text = str(raw).strip()
    return text or None


def format_serviceability_solution_lines(block: ServiceabilityBlock) -> list[str]:
    """Human-readable lines for logging or console output."""
    lines: list[str] = []
    if block.short_service_info:
        lines.append("short_service_info:")
        for part in block.short_service_info.splitlines():
            lines.append(f"  {part}" if part else "  ")
        lines.append("")
    if block.solution_reasoning:
        lines.append(block.solution_reasoning)
    if block.hub_version:
        lines.append(f"Hub version: {block.hub_version}")
    if block.afid_sag_file_version:
        lines.append(f"AFID_SAG file: {block.afid_sag_file_version}")
    if not block.solution:
        lines.append("No service actions recommended.")
        return lines
    for index, solution in enumerate(block.solution, start=1):
        units = ", ".join(solution.serviceable_unit)
        title = (solution.service_action_title or "").strip()
        action = f"service action {solution.service_action_num}"
        if title:
            action = f"{action} ({title})"
        lines.append(f"[{index}] AFID {solution.afid}, {action}, units: [{units}]")
    return lines


def serviceability_block_from_service_result(
    afid_events: list[AfidEvent],
    result: Any,
    *,
    hub_label: str = "Service hub",
    rf_event_count: int = 0,
) -> ServiceabilityBlock:
    """Build a ``ServiceabilityBlock`` from a hub result with ``service_info``."""
    grouped: dict[tuple[int, int], list[str]] = defaultdict(list)
    titles: dict[tuple[int, int], str] = {}
    service_info = getattr(result, "service_info", None) or {}

    def _action_title(info: dict[str, Any]) -> str:
        raw = info.get("title") or info.get("service_action") or info.get("ServiceAction")
        if raw is None:
            return ""
        if isinstance(raw, dict):
            return str(raw.get("title") or raw.get("text") or raw.get("name") or "").strip()
        return str(raw).strip()

    for designation, afid_map in service_info.items():
        if not isinstance(afid_map, dict):
            continue
        unit = str(designation).strip() if designation is not None else ""
        for afid_raw, info in afid_map.items():
            if not isinstance(info, dict):
                continue
            san_raw = info.get("service_action_number")
            if san_raw is None:
                continue
            try:
                afid = int(afid_raw)
                san = int(san_raw)
            except (TypeError, ValueError):
                continue
            key = (afid, san)
            if unit and unit not in grouped[key]:
                grouped[key].append(unit)
            label = _action_title(info)
            if label and key not in titles:
                titles[key] = label

    solutions = [
        ServiceabilitySolution(
            afid=afid,
            serviceable_unit=units,
            service_action_num=san,
            service_action_title=titles.get((afid, san)),
        )
        for (afid, san), units in sorted(grouped.items())
    ]
    raw_metadata = getattr(result, "afid_sag_metadata", None)
    metadata: Dict[str, Any] = raw_metadata if isinstance(raw_metadata, dict) else {}
    version_info = (
        getattr(result, "engine_version_info", None)
        or getattr(result, "isa_version_info", None)
        or getattr(result, "version_info", None)
        or {}
    )
    hub_version = _hub_version_display(version_info)
    afid_sag_file_version = _afid_sag_file_version_display(metadata)
    reasoning = (
        f"{hub_label}: {len(solutions)} recommendation(s) from {rf_event_count} Redfish event(s)."
    )
    meta_out: Optional[dict[str, Any]] = dict(metadata) if isinstance(raw_metadata, dict) else None
    short_service_info = _format_short_service_info_for_block(
        getattr(result, "short_service_info", None)
    )
    return ServiceabilityBlock(
        afid_events=list(afid_events),
        solution=solutions,
        solution_reasoning=reasoning,
        hub_version=hub_version,
        afid_sag_file_version=afid_sag_file_version,
        afid_sag_metadata=meta_out,
        short_service_info=short_service_info,
    )
