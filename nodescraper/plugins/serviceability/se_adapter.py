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
"""Map serviceability plugin models to/from Python service engine results."""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from .se_models import AfidEvent, ServiceabilityBlock, ServiceabilitySolution


def format_serviceability_solution_lines(block: ServiceabilityBlock) -> list[str]:
    """Human-readable lines for logging or console output."""
    lines: list[str] = []
    if block.solution_reasoning:
        lines.append(block.solution_reasoning)
    if not block.solution:
        lines.append("No service actions recommended.")
        return lines
    for index, solution in enumerate(block.solution, start=1):
        units = ", ".join(solution.serviceable_unit)
        lines.append(
            f"[{index}] AFID {solution.afid}, "
            f"service action {solution.service_action_num}, "
            f"units: [{units}]"
        )
    return lines


def serviceability_block_from_service_result(
    afid_events: list[AfidEvent],
    result: Any,
    *,
    engine_label: str = "Service engine",
    rf_event_count: int = 0,
) -> ServiceabilityBlock:
    """Build a :class:`ServiceabilityBlock` from an engine result with ``service_info``."""
    grouped: dict[tuple[int, int], list[str]] = defaultdict(list)
    service_info = getattr(result, "service_info", None) or {}
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

    solutions = [
        ServiceabilitySolution(
            afid=afid,
            serviceable_unit=units,
            service_action_num=san,
        )
        for (afid, san), units in sorted(grouped.items())
    ]
    metadata = getattr(result, "afid_sag_metadata", None) or {}
    version_info = (
        getattr(result, "engine_version_info", None) or getattr(result, "version_info", None) or {}
    )
    sag_pid = metadata.get("sag_pid") or metadata.get("pid") or "unknown"
    sag_revision = metadata.get("sag_revision") or metadata.get("revision") or "unknown"
    engine_version = version_info.get("version") or version_info.get("engine_version")
    version_suffix = f", engine {engine_version}" if engine_version else ""
    reasoning = (
        f"{engine_label} (SAG {sag_pid} rev {sag_revision}{version_suffix}): "
        f"{len(solutions)} recommendation(s) from {rf_event_count} Redfish event(s)."
    )
    return ServiceabilityBlock(
        afid_events=list(afid_events),
        solution=solutions,
        solution_reasoning=reasoning,
    )
