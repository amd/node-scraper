###############################################################################
#
# MIT License
#
# Copyright (c) 2025 Advanced Micro Devices, Inc.
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

import re
from typing import TYPE_CHECKING, Optional

from pydantic import BaseModel

from nodescraper.enums import EventPriority, ExecutionStatus

if TYPE_CHECKING:
    from nodescraper.models.event import Event
    from nodescraper.models.pluginresult import PluginResult


class PostActionCondition(BaseModel):
    """A single condition that, if matched, causes a post-action plugin to run.

    All specified (non-None) fields are AND'd together within one condition.
    Unspecified fields are ignored and never prevent a match.  A list of
    ``PostActionCondition`` objects is OR'd by the containing
    :class:`PostActionPluginConfig`.
    """

    plugin: Optional[str] = None
    """If set, only inspect the PluginResult whose ``source`` matches this name.
    If None, all results are candidates."""

    status: Optional[str] = None
    """If set, the result's ExecutionStatus must be >= this value.
    Accepts any :class:`~nodescraper.enums.ExecutionStatus` name
    (e.g. ``"WARNING"``, ``"ERROR"``, ``"EXECUTION_FAILURE"``)."""

    event_category: Optional[str] = None
    """If set, at least one event from analysis_result or collection_result must
    have a category equal to this value (matched after the same normalisation
    applied to event categories: strip, upper, spaces/hyphens → underscores)."""

    event_priority: Optional[str] = None
    """If set, at least one event's priority must be >= this value.
    Accepts any :class:`~nodescraper.enums.EventPriority` name
    (e.g. ``"WARNING"``, ``"ERROR"``, ``"CRITICAL"``)."""

    event_description_contains: Optional[str] = None
    """If set, at least one event's description must contain this substring
    (case-sensitive)."""

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalise_category(raw: str) -> str:
        """Apply the same normalisation used by :class:`~nodescraper.models.event.Event`."""
        normalised = str(raw).strip().upper()
        return re.sub(r"[\s-]", "_", normalised)

    def _get_all_events(self, result: PluginResult) -> list[Event]:
        """Collect events from both collection and analysis task results."""
        events: list[Event] = []
        rd = result.result_data
        if rd is None:
            return events
        if hasattr(rd, "collection_result") and rd.collection_result is not None:
            events.extend(rd.collection_result.events)
        if hasattr(rd, "analysis_result") and rd.analysis_result is not None:
            events.extend(rd.analysis_result.events)
        return events

    def _matches_result(self, result: PluginResult) -> bool:
        """Return True if *result* satisfies all specified fields (AND logic).

        Each field that is not None must be satisfied; unset fields are skipped.
        """
        # --- status check ---
        if self.status is not None:
            try:
                status_threshold = ExecutionStatus[self.status.upper()]
            except KeyError:
                return False
            if result.status < status_threshold:
                return False

        # Remaining checks all operate on events; collect them once.
        events = self._get_all_events(result)

        # --- event_category check ---
        if self.event_category is not None:
            normalised = self._normalise_category(self.event_category)
            if not any(e.category == normalised for e in events):
                return False

        # --- event_priority check ---
        if self.event_priority is not None:
            try:
                priority_threshold = EventPriority[self.event_priority.upper()]
            except KeyError:
                return False
            if not any(e.priority >= priority_threshold for e in events):
                return False

        # --- event_description_contains check ---
        if self.event_description_contains is not None:
            if not any(self.event_description_contains in e.description for e in events):
                return False

        return True

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_met(self, plugin_results: list[PluginResult]) -> bool:
        """Return True if this condition is satisfied by any of the provided results.

        If ``plugin`` is set only that plugin's result is checked; otherwise all
        results are candidates.

        Args:
            plugin_results: List of :class:`~nodescraper.models.pluginresult.PluginResult`
                objects from the primary plugin run.

        Returns:
            bool: True if at least one candidate result satisfies all specified fields.
        """
        candidates = [r for r in plugin_results if self.plugin is None or r.source == self.plugin]
        return any(self._matches_result(r) for r in candidates)
