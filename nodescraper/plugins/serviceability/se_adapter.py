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
"""Map node-scraper serviceability models to/from the AMD serviceability-engine API."""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from .se_models import AfidEvent, ServiceabilityBlock, ServiceabilitySolution

_DEFAULT_SOLUTION_TIERS = (
    "primary_fru_events",
    "secondary_actions",
)


def afid_events_to_engine_input(afid_events: list[AfidEvent]) -> list[dict[str, Any]]:
    """Convert plugin AFID events to serviceability-engine wire-format dicts.

    The engine triages on (afid, location, count). Duplicate (afid, unit) pairs
    are merged by summing counts. Timestamp is preserved only on the plugin side.
    """
    counts: dict[tuple[str, str], int] = defaultdict(int)
    for event in afid_events:
        key = (str(event.afid), event.serviceable_unit)
        counts[key] += 1
    return [
        {"afid": afid, "location": location, "count": count}
        for (afid, location), count in sorted(counts.items())
    ]


def recommendations_from_report_dict(
    report: dict[str, Any],
    *,
    solution_tiers: tuple[str, ...] = _DEFAULT_SOLUTION_TIERS,
) -> list[dict[str, Any]]:
    """Derive grouped recommendations from an :func:`serviceability_engine.api.analyze` report."""
    if "recommendations" in report:
        return list(report["recommendations"])

    grouped: dict[tuple[int, int], list[str]] = defaultdict(list)
    for tier in solution_tiers:
        for row in report.get(tier, []):
            if not isinstance(row, dict):
                continue
            afid = int(row.get("afid", 0))
            location = str(row.get("location", "")).strip()
            action_num = _action_num_from_row(row)
            if not location or action_num is None:
                continue
            key = (afid, action_num)
            if location not in grouped[key]:
                grouped[key].append(location)

    return [
        {
            "afid": afid,
            "locations": locations,
            "service_action_num": action_num,
        }
        for (afid, action_num), locations in sorted(grouped.items())
    ]


def serviceability_block_from_engine(
    afid_events: list[AfidEvent],
    report: dict[str, Any],
    *,
    recommendations: list[dict[str, Any]] | None = None,
) -> ServiceabilityBlock:
    """Build the ANC ``serviceability`` block from an engine analysis report."""
    recs = (
        recommendations if recommendations is not None else recommendations_from_report_dict(report)
    )
    solutions = [
        ServiceabilitySolution(
            afid=int(item["afid"]),
            serviceable_unit=list(item["locations"]),
            service_action_num=int(item["service_action_num"]),
        )
        for item in recs
    ]
    reasoning = _build_solution_reasoning(afid_events, solutions, report)
    return ServiceabilityBlock(
        afid_events=list(afid_events),
        solution=solutions,
        solution_reasoning=reasoning,
    )


def _action_num_from_row(row: dict[str, Any]) -> int | None:
    if "service_action_num" in row:
        return int(row["service_action_num"])
    service_action = row.get("service_action")
    if isinstance(service_action, dict) and "id" in service_action:
        return int(service_action["id"])
    afid_entry = row.get("afid_entry")
    if isinstance(afid_entry, dict) and "service_action_num" in afid_entry:
        return int(afid_entry["service_action_num"])
    return None


def _build_solution_reasoning(
    afid_events: list[AfidEvent],
    solutions: list[ServiceabilitySolution],
    report: dict[str, Any],
) -> str:
    sag_pid = report.get("sag_pid") or "unknown"
    sag_revision = report.get("sag_revision") or "unknown"
    return (
        f"Serviceability engine (SAG {sag_pid} rev {sag_revision}): "
        f"{len(solutions)} recommendation(s) from {len(afid_events)} input event(s)."
    )
