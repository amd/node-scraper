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

from .se_models import (
    HubTriageResult,
    PrioritizedServiceAction,
    ServiceabilityBlock,
    ServiceabilitySolution,
)


def service_action_identity(action: PrioritizedServiceAction) -> tuple[int, str, int]:
    """Return the Hub row identity used to match top vs results entries."""
    return (action.afid, action.location, action.service_action_num)


def _hub_triage_identity(row: HubTriageResult) -> tuple[int, str, int]:
    return (row.afid, row.location, row.service_action_num)


def _triage_row_to_action(rank: int, row: HubTriageResult) -> PrioritizedServiceAction:
    return PrioritizedServiceAction(
        rank=rank,
        afid=row.afid,
        location=row.location,
        count=row.count,
        service_action_num=row.service_action_num,
        service_action_title=row.service_action_title,
        service_action_category=row.service_action_category,
        priority=row.priority,
        sa_severity=row.sa_severity,
        tier=row.tier,
        tier_label=row.tier_label,
        fru=row.fru,
        fru_rank=row.fru_rank,
        hub_sort_priority=row.hub_sort_priority,
        multi_mask=row.multi_mask,
        afid_summary=row.afid_summary,
        service_action_steps=list(row.service_action_steps),
    )


def _solution_to_action(rank: int, solution: ServiceabilitySolution) -> PrioritizedServiceAction:
    return PrioritizedServiceAction(
        rank=rank,
        afid=solution.afid,
        location=solution.serviceable_unit[0] if solution.serviceable_unit else "",
        count=1,
        service_action_num=solution.service_action_num,
        service_action_title=solution.service_action_title,
        service_action_category=None,
        priority=None,
        sa_severity=None,
        tier=None,
        tier_label=solution.service_action_tier,
        fru=None,
        fru_rank=None,
        hub_sort_priority=None,
        multi_mask=None,
        afid_summary=solution.afid_summary,
        service_action_steps=[],
        serviceable_units=list(solution.serviceable_unit),
    )


def _optional_int(value: Any) -> Optional[int]:
    """Return value as an int when it is numeric.

    Args:
        value: Field from an AFSE triage row.

    Returns:
        The integer value, or None when value is missing or not numeric.
    """
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _afse_service_action(row: dict[str, Any]) -> dict[str, Any]:
    """Return the service_action object on an AFSE triage row.

    Args:
        row: One AFSE triage.top or triage.results entry.

    Returns:
        The service_action mapping, or an empty mapping when it is absent.
    """
    service_action = row.get("service_action")
    if isinstance(service_action, dict):
        return service_action
    return {}


def _afse_action_title(row: dict[str, Any]) -> Optional[str]:
    """Return the service action title from an AFSE triage row.

    Args:
        row: One AFSE triage.top or triage.results entry.

    Returns:
        The title text, or None when the row has no title.
    """
    service_action = _afse_service_action(row)
    for candidate in (service_action.get("title"), row.get("service_action_title")):
        if candidate is None:
            continue
        text = str(candidate).strip()
        if text:
            return text
    return None


def _afse_action_steps(row: dict[str, Any]) -> list[str]:
    """Return service action step descriptions from an AFSE triage row.

    Args:
        row: One AFSE triage.top or triage.results entry.

    Returns:
        Step description strings in AFSE order.
    """
    steps = _afse_service_action(row).get("steps")
    if not isinstance(steps, list):
        return []
    descriptions: list[str] = []
    for step in steps:
        if not isinstance(step, dict):
            continue
        description = step.get("description")
        if description is None:
            continue
        text = str(description).strip()
        if text:
            descriptions.append(text)
    return descriptions


def _action_from_afse_row(rank: int, row: dict[str, Any]) -> Optional[PrioritizedServiceAction]:
    """Map one AFSE triage row to a table action.

    Args:
        rank: 1-based position of this row inside triage.top.
        row: One AFSE triage.top entry.

    Returns:
        The table action, or None when the row has no AFID, action number, or location.
    """
    afid_raw = row.get("afid", row.get("afid_num"))
    san_raw = row.get("service_action_num")
    location = row.get("location") or row.get("serviceable_unit")
    if afid_raw is None or san_raw is None or location is None:
        return None
    try:
        afid = int(afid_raw)
        service_action_num = int(san_raw)
    except (TypeError, ValueError):
        return None
    location_text = str(location).strip()
    if not location_text:
        return None
    service_action = _afse_service_action(row)
    tier_label = row.get("tier_label")
    if tier_label is not None:
        tier_label = str(tier_label).strip() or None
    category = service_action.get("category")
    category_text = (
        str(category).strip() if category is not None and str(category).strip() else None
    )
    return PrioritizedServiceAction(
        rank=rank,
        afid=afid,
        location=location_text,
        count=max(1, _optional_int(row.get("count")) or 1),
        service_action_num=service_action_num,
        service_action_title=_afse_action_title(row),
        service_action_category=category_text,
        priority=_optional_int(row.get("priority")),
        sa_severity=_optional_int(row.get("sa_severity"))
        or _optional_int(service_action.get("severity")),
        tier=_optional_int(row.get("tier")),
        tier_label=tier_label,
        hub_sort_priority=_optional_int(
            row.get("se_sort_priority") or row.get("hub_sort_priority")
        ),
        multi_mask=_optional_int(row.get("multi_mask")),
        service_action_steps=_afse_action_steps(row),
    )


def actions_from_afse_triage_top(block: ServiceabilityBlock) -> list[PrioritizedServiceAction]:
    """Return table rows for AFSE triage.top.

    Args:
        block: Serviceability block that may hold the raw hub analyze response.

    Returns:
        One action per AFSE triage.top entry. Empty when that list is absent.
    """
    response = block.hub_analyze_response
    if not isinstance(response, dict):
        return []
    triage = response.get("triage")
    if not isinstance(triage, dict):
        return []
    top = triage.get("top")
    if not isinstance(top, list):
        return []
    actions: list[PrioritizedServiceAction] = []
    for index, row in enumerate(top, start=1):
        if not isinstance(row, dict):
            continue
        action = _action_from_afse_row(index, row)
        if action is not None:
            actions.append(action)
    return actions


def _afse_triage_section(block: ServiceabilityBlock) -> Optional[dict[str, Any]]:
    """Return the AFSE triage object when the hub response includes one.

    Args:
        block: Serviceability block populated by hub analysis.

    Returns:
        The triage mapping, or None when the response has no triage section.
    """
    response = block.hub_analyze_response
    if not isinstance(response, dict):
        return None
    triage = response.get("triage")
    if not isinstance(triage, dict):
        return None
    return triage


def afse_top_action_missing(block: ServiceabilityBlock) -> bool:
    """Return whether an AFSE triage section has no top action.

    Args:
        block: Serviceability block populated by hub analysis.

    Returns:
        True when triage is present and triage.top has no usable action.
    """
    if _afse_triage_section(block) is None:
        return False
    return not actions_from_afse_triage_top(block)


def build_top_service_actions(block: ServiceabilityBlock) -> list[PrioritizedServiceAction]:
    """Return the AFSE triage.top service actions for display.

    Args:
        block: Serviceability block populated by hub analysis.

    Returns:
        Actions from AFSE triage.top when that list has entries. Empty when triage
        is present but triage.top is empty. Parsed hub rows are used when the
        response has no triage section.
    """
    afse_top = actions_from_afse_triage_top(block)
    if afse_top:
        return afse_top
    if _afse_triage_section(block) is not None:
        return []
    if block.hub_top_results:
        rank_by_identity = {
            _hub_triage_identity(row): rank
            for rank, row in enumerate(block.hub_triage_results, start=1)
        }
        top_actions: list[PrioritizedServiceAction] = []
        for index, row in enumerate(block.hub_top_results, start=1):
            rank = rank_by_identity.get(_hub_triage_identity(row), index)
            top_actions.append(_triage_row_to_action(rank, row))
        return top_actions
    if block.hub_triage_results:
        return [_triage_row_to_action(1, block.hub_triage_results[0])]
    if block.solution:
        return [_solution_to_action(1, block.solution[0])]
    return []


def build_prioritized_service_actions(
    block: ServiceabilityBlock,
) -> list[PrioritizedServiceAction]:
    """Return hub-ranked service actions from triage.results order."""
    if block.hub_triage_results:
        return [
            _triage_row_to_action(rank, row)
            for rank, row in enumerate(block.hub_triage_results, start=1)
        ]
    return [
        _solution_to_action(rank, solution) for rank, solution in enumerate(block.solution, start=1)
    ]


def split_recommendation_actions(
    block: ServiceabilityBlock,
) -> tuple[list[PrioritizedServiceAction], list[PrioritizedServiceAction]]:
    """Split Hub triage.top service actions from lower-priority triage.results rows."""
    prioritized = build_prioritized_service_actions(block)
    top = build_top_service_actions(block)
    if not prioritized:
        return top, []
    if not top:
        if _afse_triage_section(block) is not None:
            return [], prioritized
        return [prioritized[0]], prioritized[1:]

    top_sort_priorities = {
        action.hub_sort_priority for action in top if action.hub_sort_priority is not None
    }
    if top_sort_priorities:
        additional = [
            action for action in prioritized if action.hub_sort_priority not in top_sort_priorities
        ]
        return top, additional

    top_identities = {service_action_identity(action) for action in top}
    additional = [
        action for action in prioritized if service_action_identity(action) not in top_identities
    ]
    return top, additional


def top_action_summary(
    block: ServiceabilityBlock,
    system_name: str,
    analyzed_at: str,
) -> dict[str, Any]:
    """Build a top-service-action summary payload from a hub result.

    Args:
        block: Serviceability block returned by the hub.
        system_name: Name of the analyzed system.
        analyzed_at: ISO timestamp for when analysis ran.

    Returns:
        System name, analysis time, hub and SAG versions, AFID event count, and the
        top service action(s). Ties for the top rank are all included.
    """
    top, _ = split_recommendation_actions(block)
    return {
        "system_name": system_name,
        "analyzed_at": analyzed_at,
        "hub_version": block.hub_version,
        "afid_sag_file_version": block.afid_sag_file_version,
        "afid_event_count": len(block.afid_events),
        "top_service_actions": [
            action.model_dump(mode="json", exclude_none=True) for action in top
        ],
    }


def export_serviceability_json(block: ServiceabilityBlock) -> Optional[dict[str, Any]]:
    """Return the AFSE analyze payload written to serviceability.json.

    Args:
        block: Serviceability block that may hold the raw hub analyze response.

    Returns:
        The hub analyze response, or None when AFSE did not return one.
    """
    if block.hub_analyze_response is None:
        return None
    return dict(block.hub_analyze_response)
