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

from collections import defaultdict
from typing import Any, Optional

from .se_models import AfidEvent, ServiceabilityBlock, ServiceabilitySolution


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
    """Build a short AFID_SAG file identity string from hub ``afid_sag_metadata``."""
    if not isinstance(metadata, dict) or not metadata:
        return None
    pid = metadata.get("sag_pid") or metadata.get("pid")
    rev = metadata.get("sag_revision") or metadata.get("revision")
    extra = (
        metadata.get("sag_version")
        or metadata.get("file_version")
        or metadata.get("schema_version")
    )
    parts: list[str] = []
    if pid and str(pid).strip():
        parts.append(f"PID {str(pid).strip()}")
    if rev and str(rev).strip():
        parts.append(f"revision {str(rev).strip()}")
    if extra and str(extra).strip():
        ex = str(extra).strip()
        if ex not in (str(pid or "").strip(), str(rev or "").strip()):
            parts.append(f"version {ex}")
    if not parts:
        return None
    return ", ".join(parts)


def format_serviceability_solution_lines(block: ServiceabilityBlock) -> list[str]:
    """Human-readable lines for logging or console output."""
    lines: list[str] = []
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
    engine_label: str = "Service hub",
    rf_event_count: int = 0,
) -> ServiceabilityBlock:
    """Build a :class:`ServiceabilityBlock` from a hub result with ``service_info``."""
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
    metadata = getattr(result, "afid_sag_metadata", None) or {}
    version_info = (
        getattr(result, "engine_version_info", None)
        or getattr(result, "isa_version_info", None)
        or getattr(result, "version_info", None)
        or {}
    )
    hub_version = _hub_version_display(version_info)
    afid_sag_file_version = _afid_sag_file_version_display(metadata)
    reasoning = f"{engine_label}: {len(solutions)} recommendation(s) from {rf_event_count} Redfish event(s)."
    return ServiceabilityBlock(
        afid_events=list(afid_events),
        solution=solutions,
        solution_reasoning=reasoning,
        hub_version=hub_version,
        afid_sag_file_version=afid_sag_file_version,
    )
