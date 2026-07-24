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

from .afid_sag_lookup import (
    afid_summary_from_sag,
    load_afid_sag_data,
    service_action_label_from_sag,
    service_action_step_descriptions_from_sag,
)
from .se_models import (
    AfidEvent,
    HubTriageResult,
    ServiceabilityBlock,
    ServiceabilitySolution,
)

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


def _load_afid_sag_data(path: Optional[str]) -> Optional[dict[str, Any]]:
    return load_afid_sag_data(path)


def _afid_summary_from_sag(afid: int, sag: Optional[dict[str, Any]]) -> Optional[str]:
    return afid_summary_from_sag(afid, sag)


def _service_action_label_from_sag(
    service_action_num: int,
    sag: Optional[dict[str, Any]],
) -> Optional[str]:
    return service_action_label_from_sag(service_action_num, sag)


def _service_action_entry_from_sag(
    service_action_num: int,
    sag: Optional[dict[str, Any]],
) -> Optional[dict[str, Any]]:
    from .afid_sag_lookup import service_action_entry_from_sag

    return service_action_entry_from_sag(service_action_num, sag)


def _optional_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _hub_triage_result_from_row(
    row: dict[str, Any],
    sag: Optional[dict[str, Any]],
) -> Optional[HubTriageResult]:
    afid_raw = row.get("afid_num", row.get("afid"))
    san_raw = row.get("service_action_num")
    location = row.get("location") or row.get("serviceable_unit")
    if afid_raw is None or san_raw is None or location is None:
        return None
    try:
        afid = int(afid_raw)
        san = int(san_raw)
    except (TypeError, ValueError):
        return None
    location_text = str(location).strip()
    if not location_text:
        return None
    sa_entry = _service_action_entry_from_sag(san, sag)
    title = row.get("service_action_title") or row.get("service_action")
    if title is not None:
        title = str(title).strip() or None
    if not title:
        title = _service_action_label_from_sag(san, sag)
    category = None
    sa_severity = None
    if sa_entry:
        raw_cat = sa_entry.get("category")
        if raw_cat is not None and str(raw_cat).strip():
            category = str(raw_cat).strip()
        sa_severity = _optional_int(sa_entry.get("severity"))
    tier_label = row.get("tier_label")
    if tier_label is not None:
        tier_label = str(tier_label).strip() or None
    if tier_label is None and row.get("tier") is not None:
        tier_label = str(row.get("tier"))
    fru = row.get("fru")
    if fru is not None:
        fru = str(fru).strip() or None
    return HubTriageResult(
        afid=afid,
        location=location_text,
        count=max(1, _optional_int(row.get("count")) or 1),
        service_action_num=san,
        tier=_optional_int(row.get("tier")),
        tier_label=tier_label,
        fru=fru,
        fru_rank=_optional_int(row.get("fru_rank")),
        priority=_optional_int(row.get("priority")),
        sa_severity=_optional_int(row.get("sa_severity")),
        hub_sort_priority=_optional_int(
            row.get("se_sort_priority") or row.get("hub_sort_priority")
        ),
        multi_mask=_optional_int(row.get("multi_mask")),
        service_action_title=title,
        service_action_category=category,
        service_action_severity=sa_severity,
        service_action_steps=service_action_step_descriptions_from_sag(san, sag),
        afid_summary=_afid_summary_from_sag(afid, sag),
    )


def _format_hub_triage_result_lines(index: int, row: HubTriageResult) -> list[str]:
    lines = [f"[{index}] AFID {row.afid} @ {row.location} (count={row.count})"]
    if row.afid_summary:
        lines.append(f"  fault: {row.afid_summary}")
    fru_bits = []
    if row.fru:
        fru_bits.append(row.fru)
    if row.fru_rank is not None:
        fru_bits.append(f"rank {row.fru_rank}")
    if fru_bits:
        lines.append(f"  FRU: {' '.join(fru_bits)}")
    meta_bits = []
    if row.priority is not None:
        meta_bits.append(f"priority={row.priority}")
    if row.sa_severity is not None:
        meta_bits.append(f"SA severity={row.sa_severity}")
    if row.tier_label:
        tier_bit = f"tier={row.tier_label}"
        if row.tier is not None:
            tier_bit = f"{tier_bit} ({row.tier})"
        meta_bits.append(tier_bit)
    if row.hub_sort_priority is not None:
        meta_bits.append(f"sort=0x{row.hub_sort_priority:08x}")
    if row.multi_mask is not None:
        meta_bits.append(f"multi_mask={row.multi_mask}")
    if meta_bits:
        lines.append(f"  {'; '.join(meta_bits)}")
    action_bits = [f"service action {row.service_action_num}"]
    if row.service_action_title:
        action_bits.append(f'"{row.service_action_title}"')
    if row.service_action_category:
        action_bits.append(f"[{row.service_action_category}]")
    if row.service_action_severity is not None:
        action_bits.append(f"SA severity={row.service_action_severity}")
    lines.append(f"  {' '.join(action_bits)}")
    for step_index, step in enumerate(row.service_action_steps):
        lines.append(f"    step {step_index}: {step}")
    return lines


def _format_service_action_phrase(solution: ServiceabilitySolution) -> str:
    title = (solution.service_action_title or "").strip()
    tier = (solution.service_action_tier or "").strip()
    base = f"service action {solution.service_action_num}"
    if title:
        base = f'{base}: "{title}"'
    if tier:
        base = f"{base} ({tier} tier)"
    return base


def format_serviceability_solution_lines(block: ServiceabilityBlock) -> list[str]:
    """Human-readable lines for logging or console output."""
    lines: list[str] = []
    if block.solution_reasoning:
        lines.append(block.solution_reasoning)
    if block.hub_version:
        lines.append(f"Hub version: {block.hub_version}")
    if block.afid_sag_file_version:
        lines.append(f"AFID_SAG file: {block.afid_sag_file_version}")
    if block.hub_triage_results:
        lines.append("Hub triage results:")
        for index, row in enumerate(block.hub_triage_results, start=1):
            lines.extend(_format_hub_triage_result_lines(index, row))
        return lines
    if block.short_service_info:
        lines.append("short_service_info:")
        for part in block.short_service_info.splitlines():
            lines.append(f"  {part}" if part else "  ")
        lines.append("")
    if not block.solution:
        lines.append("No service actions recommended.")
        return lines
    for index, solution in enumerate(block.solution, start=1):
        units = ", ".join(solution.serviceable_unit)
        summary = f" ({solution.afid_summary})" if solution.afid_summary else ""
        action = _format_service_action_phrase(solution)
        lines.append(f"[{index}] AFID {solution.afid}{summary}: {action}, units: [{units}]")
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


def serviceability_block_from_entry_point_hub(
    afid_events: list[AfidEvent],
    hub_result: dict[str, Any],
    *,
    hub_label: str = "Service hub",
    rf_event_count: int = 0,
    afid_sag_path: Optional[str] = None,
) -> ServiceabilityBlock:
    """Build a ServiceabilityBlock from a registered entry-point hub analyze() response."""
    hub_name = str(hub_result.get("engine") or hub_label)
    hub_version_raw = hub_result.get("engine_version")
    results = hub_result.get("results") or []
    sag = _load_afid_sag_data(afid_sag_path)

    grouped: dict[tuple[int, int], list[str]] = defaultdict(list)
    titles: dict[tuple[int, int], str] = {}
    tiers: dict[tuple[int, int], str] = {}
    summaries: dict[int, str] = {}

    for row in results:
        if not isinstance(row, dict):
            continue
        afid_raw = row.get("afid_num", row.get("afid"))
        san_raw = row.get("service_action_num")
        location = row.get("location") or row.get("serviceable_unit")
        if afid_raw is None or san_raw is None:
            continue
        try:
            afid = int(afid_raw)
            san = int(san_raw)
        except (TypeError, ValueError):
            continue
        unit = str(location).strip() if location is not None else ""
        key = (afid, san)
        if unit and unit not in grouped[key]:
            grouped[key].append(unit)
        row_title = row.get("service_action_title") or row.get("service_action")
        if row_title is not None and key not in titles:
            text = str(row_title).strip()
            if text:
                titles[key] = text
        tier_label = row.get("tier_label") or row.get("tier")
        if tier_label is not None and key not in tiers:
            text = str(tier_label).strip()
            if text:
                tiers[key] = text
        if afid not in summaries:
            summary = _afid_summary_from_sag(afid, sag)
            if summary:
                summaries[afid] = summary

    solutions = []
    for (afid, san), units in sorted(grouped.items()):
        title = titles.get((afid, san)) or _service_action_label_from_sag(san, sag)
        if not title:
            afid_map = (sag or {}).get("afid") if isinstance(sag, dict) else None
            if isinstance(afid_map, dict):
                afid_entry = afid_map.get(str(afid))
                if isinstance(afid_entry, dict):
                    fallback = afid_entry.get("service_action")
                    if fallback is not None and str(fallback).strip():
                        title = str(fallback).strip()
        solutions.append(
            ServiceabilitySolution(
                afid=afid,
                serviceable_unit=units,
                service_action_num=san,
                service_action_title=title,
                service_action_tier=tiers.get((afid, san)),
                afid_summary=summaries.get(afid),
            )
        )

    hub_version = str(hub_version_raw).strip() if hub_version_raw else None
    reasoning = (
        f"{hub_name}: {len(solutions)} recommendation(s) from "
        f"{rf_event_count} Redfish event(s), {len(results)} triage row(s)."
    )
    triage_results: list[HubTriageResult] = []
    for row in results:
        if not isinstance(row, dict):
            continue
        parsed = _hub_triage_result_from_row(row, sag)
        if parsed is not None:
            triage_results.append(parsed)
    sag_metadata = None
    afid_sag_file_version = None
    if sag:
        sag_metadata = {
            "pid": sag.get("pid"),
            "revision": sag.get("revision"),
            "variant": sag.get("variant"),
        }
        afid_sag_file_version = _afid_sag_file_version_display(sag_metadata)

    return ServiceabilityBlock(
        afid_events=list(afid_events),
        solution=solutions,
        solution_reasoning=reasoning,
        hub_version=hub_version,
        afid_sag_file_version=afid_sag_file_version,
        afid_sag_metadata=sag_metadata,
        hub_triage_results=triage_results,
    )
