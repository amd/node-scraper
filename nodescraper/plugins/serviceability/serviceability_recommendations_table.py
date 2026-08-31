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

import sys
from textwrap import wrap
from typing import Optional

from .se_models import PrioritizedServiceAction, ServiceabilityBlock
from .serviceability_api import split_recommendation_actions

RECOMMENDATION_TABLE_HEADERS: tuple[str, ...] = (
    "Rank",
    "Priority",
    "SA Sev",
    "Tier",
    "Units",
    "Service Action",
    "Steps",
)

PRIMARY_RECOMMENDATION_TITLE = "Top Hub service action"
ADDITIONAL_RECOMMENDATIONS_TITLE = "Additional Hub service actions"
ADDITIONAL_RECOMMENDATIONS_NOTE = (
    "Lower-priority follow-on actions if the top service action does not resolve the issue."
)

RECOMMENDATION_TABLE_MAX_WIDTHS: dict[str, int] = {
    "Rank": 4,
    "Priority": 8,
    "SA Sev": 6,
    "Tier": 10,
    "Units": 28,
    "Service Action": 40,
    "Steps": 96,
}


def _recommendation_section_title(
    title: str,
    actions: list[PrioritizedServiceAction],
) -> str:
    if not actions:
        return title
    ranks = [action.rank for action in actions if action.rank]
    if len(actions) == 1 and ranks:
        return f"{title} (rank {ranks[0]})"
    if ranks:
        return (
            f"{title} (ranks {min(ranks)}-{max(ranks)}, "
            f"{len(actions)} item{'s' if len(actions) != 1 else ''})"
        )
    return f"{title} ({len(actions)} item{'s' if len(actions) != 1 else ''})"


def _short_serviceable_unit(location: str) -> str:
    text = str(location).strip().rstrip("/")
    if not text:
        return ""
    return text.rsplit("/", 1)[-1]


def _recommendation_units_cell(action: PrioritizedServiceAction) -> str:
    units = list(action.serviceable_units or [])
    if not units and action.location:
        units = [action.location]
    return ", ".join(_short_serviceable_unit(unit) for unit in units if unit)


def _recommendation_service_action_cell(action: PrioritizedServiceAction) -> str:
    title = (action.service_action_title or "").strip()
    if title:
        return f"{action.afid}: {title}"
    return f"{action.afid}: SA {action.service_action_num}"


def _recommendation_steps_cell(action: PrioritizedServiceAction) -> str:
    steps = [str(step).strip() for step in action.service_action_steps if str(step).strip()]
    if not steps:
        return ""
    return "; ".join(f"{index}: {step}" for index, step in enumerate(steps))


def _recommendation_table_row(action: PrioritizedServiceAction) -> list[str]:
    priority = "" if action.priority is None else str(action.priority)
    sa_severity = "" if action.sa_severity is None else str(action.sa_severity)
    tier = (action.tier_label or "").strip()
    return [
        str(action.rank),
        priority,
        sa_severity,
        tier,
        _recommendation_units_cell(action),
        _recommendation_service_action_cell(action),
        _recommendation_steps_cell(action),
    ]


def render_recommendations_table(
    actions: list[PrioritizedServiceAction],
    *,
    headers: tuple[str, ...] = RECOMMENDATION_TABLE_HEADERS,
    max_widths: Optional[dict[str, int]] = None,
) -> str:
    """Render prioritized Hub recommendations as a bordered ASCII table."""
    if max_widths is None:
        max_widths = dict(RECOMMENDATION_TABLE_MAX_WIDTHS)
    rows = [_recommendation_table_row(action) for action in actions]
    return _gen_str_table(list(headers), rows, max_widths=max_widths)


def render_recommendations_section(
    title: str,
    actions: list[PrioritizedServiceAction],
    *,
    note: Optional[str] = None,
) -> str:
    """Render a titled recommendations block with an optional explanatory note."""
    if not actions:
        return ""
    lines = [title]
    if note:
        lines.append(note)
    lines.append(render_recommendations_table(actions))
    return "\n".join(lines)


def render_serviceability_recommendation_tables(block: ServiceabilityBlock) -> str:
    """Render primary and additional Hub recommendation tables."""
    primary, additional = split_recommendation_actions(block)
    sections: list[str] = []
    primary_section = render_recommendations_section(
        _recommendation_section_title(PRIMARY_RECOMMENDATION_TITLE, primary),
        primary,
    )
    if primary_section:
        sections.append(primary_section)
    additional_section = render_recommendations_section(
        _recommendation_section_title(ADDITIONAL_RECOMMENDATIONS_TITLE, additional),
        additional,
        note=ADDITIONAL_RECOMMENDATIONS_NOTE,
    )
    if additional_section:
        sections.append(additional_section)
    if not sections:
        return ""
    return "\n\n".join(sections)


def emit_serviceability_recommendation_tables(block: ServiceabilityBlock) -> None:
    """Print Hub recommendation tables to stdout."""
    output = render_serviceability_recommendation_tables(block)
    if not output:
        return
    sys.stdout.write(f"\n{output}\n")


def _gen_str_table(
    headers: list[str],
    rows: list[list[str]],
    max_widths: Optional[dict[str, int]] = None,
) -> str:
    max_widths = max_widths or {}
    norm_rows: list[list[str]] = [[str(cell) for cell in row] for row in rows]
    ncols = len(headers)

    raw_widths: list[int] = [len(header) for header in headers]
    for norm_row in norm_rows:
        for index, cell in enumerate(norm_row):
            for part in cell.splitlines() or [""]:
                if len(part) > raw_widths[index]:
                    raw_widths[index] = len(part)

    target_widths: list[int] = []
    for index, header in enumerate(headers):
        cap = max_widths.get(header)
        if cap is None:
            target_widths.append(raw_widths[index])
        else:
            target_widths.append(max(len(header), min(raw_widths[index], cap)))

    wrapped_rows: list[list[list[str]]] = []
    for norm_row in norm_rows:
        wrapped_cells: list[list[str]] = []
        for index, cell in enumerate(norm_row):
            cell_lines: list[str] = []
            for paragraph in cell.splitlines() or [""]:
                cell_lines.extend(wrap(paragraph, width=target_widths[index]) or [""])
            wrapped_cells.append(cell_lines)
        wrapped_rows.append(wrapped_cells)

    col_widths: list[int] = []
    for index in range(ncols):
        widest_line = len(headers[index])
        for wrapped_row in wrapped_rows:
            for line in wrapped_row[index]:
                if len(line) > widest_line:
                    widest_line = len(line)
        col_widths.append(widest_line)

    border = "+" + "+".join("-" * (width + 2) for width in col_widths) + "+"

    def render_physical_row(parts: list[str]) -> str:
        return "| " + " | ".join(part.ljust(width) for part, width in zip(parts, col_widths)) + " |"

    table_lines = [border, render_physical_row(headers), border]
    for wrapped_row in wrapped_rows:
        height = max(len(cell_lines) for cell_lines in wrapped_row)
        for line_index in range(height):
            parts = [
                wrapped_row[column][line_index] if line_index < len(wrapped_row[column]) else ""
                for column in range(ncols)
            ]
            table_lines.append(render_physical_row(parts))
    table_lines.append(border)
    return "\n".join(table_lines)
