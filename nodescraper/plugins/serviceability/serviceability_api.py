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

from typing import Any

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


def build_top_service_actions(block: ServiceabilityBlock) -> list[PrioritizedServiceAction]:
    """Return Hub triage.top service actions with ranks from triage.results order."""
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


def prepare_serviceability_block_for_export(
    block: ServiceabilityBlock,
) -> ServiceabilityBlock:
    """Return a JSON-safe serviceability block without duplicate hub triage rows."""
    return block.model_copy(update={"hub_triage_results": [], "hub_top_results": []})


def export_serviceability_json(block: ServiceabilityBlock) -> dict[str, Any]:
    """Serialize serviceability.json with raw Hub output and no duplicate triage rows."""
    exported = prepare_serviceability_block_for_export(block)
    return exported.model_dump(
        mode="json",
        exclude={"hub_triage_results", "hub_top_results"},
    )
