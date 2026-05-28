###############################################################################
#
# MIT License
#
# Copyright (C) 2026 Advanced Micro Devices, Inc.
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

"""First-match-wins priority override rules for :class:`~nodescraper.models.event.Event`."""

from __future__ import annotations

import re
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from nodescraper.enums import EventPriority
from nodescraper.models.event import Event

__all__ = [
    "NO_CHANGE",
    "PriorityOverrideRule",
    "apply_priority_override_rules",
]

NO_CHANGE = "NO_CHANGE"


def _normalize_category(category: str) -> str:
    category = str(category).strip().upper()
    return re.sub(r"[\s-]", "_", category)


class PriorityOverrideRule(BaseModel):
    """One override rule; first matching rule wins when applied to an event list."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    match_all: bool = False
    new_priority: str
    description: Optional[str] = None
    message: Optional[str] = None
    event_category: Optional[str] = None

    @field_validator("new_priority", mode="before")
    @classmethod
    def _validate_new_priority_token(cls, value: object) -> str:
        if value is None:
            raise ValueError("new_priority is required")
        if value == NO_CHANGE:
            return NO_CHANGE
        if isinstance(value, EventPriority):
            return value.name
        if not isinstance(value, str):
            raise ValueError("new_priority must be a string or EventPriority")
        upper = value.upper()
        if upper == NO_CHANGE:
            return NO_CHANGE
        if upper not in {p.name for p in EventPriority}:
            raise ValueError(
                f"new_priority must be {NO_CHANGE} or one of " f"{[p.name for p in EventPriority]}"
            )
        return upper

    @model_validator(mode="after")
    def _require_match_all_or_selectors(self) -> PriorityOverrideRule:
        if self.match_all:
            return self
        if self.description is None and self.message is None and self.event_category is None:
            raise ValueError(
                "set match_all=True or provide at least one selector among "
                "description, message, and event_category"
            )
        return self

    def matches_event(self, event: Event) -> bool:
        """Return True if this rule applies to *event*."""
        if self.match_all:
            return True
        if self.description is not None and event.description != self.description:
            return False
        if self.message is not None:
            match_content = event.data.get("match_content", "")
            if not isinstance(match_content, str):
                match_content = str(match_content)
            if self.message not in match_content and self.message not in event.description:
                return False
        if self.event_category is not None:
            if _normalize_category(self.event_category) != _normalize_category(event.category):
                return False
        return True


def apply_priority_override_rules(events: list[Event], rules: list[dict]) -> None:
    """Apply *rules* in order to each event in *events* (in place); first match wins.

    ``new_priority`` may be :data:`NO_CHANGE` to keep the current priority while still
    stopping further rules for that event.
    """
    parsed = [PriorityOverrideRule.model_validate(r) for r in rules]
    for event in events:
        for rule in parsed:
            if not rule.matches_event(event):
                continue
            if rule.new_priority != NO_CHANGE:
                event.priority = EventPriority[rule.new_priority]
            break
