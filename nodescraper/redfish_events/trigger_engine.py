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
"""Sliding-window trigger logic for batched serviceability analysis."""
from __future__ import annotations

import asyncio
import inspect
import logging
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Optional, Union

from pydantic import BaseModel, Field

from .models import RedfishEvent

logger = logging.getLogger(__name__)

TriggerCallback = Callable[[str, list[RedfishEvent]], Union[None, Awaitable[None]]]
NowFn = Callable[[], datetime]


class TriggerConfig(BaseModel):
    """When to run serviceability analysis for a burst of ingest events."""

    min_events: int = Field(default=3, ge=1, description="Events required within the window")
    window_seconds: float = Field(default=10.0, gt=0, description="Sliding window size in seconds")
    cooldown_seconds: float = Field(
        default=60.0,
        ge=0,
        description="Minimum seconds between analysis runs for the same target",
    )


@dataclass
class _TargetWindow:
    events: deque[tuple[datetime, RedfishEvent]] = field(default_factory=deque)
    cooldown_until: Optional[datetime] = None


class TriggerEngine:
    """Fire analysis when enough events arrive within a sliding time window."""

    def __init__(
        self,
        config: TriggerConfig,
        on_trigger: TriggerCallback,
        *,
        clock_fn: NowFn = lambda: datetime.now(UTC),
    ) -> None:
        self.config = config
        self.on_trigger = on_trigger
        self._now = clock_fn
        self._targets: dict[str, _TargetWindow] = {}
        self._lock = asyncio.Lock()

    async def handle_event(self, event: RedfishEvent) -> bool:
        """Record one event and invoke on_trigger when the window threshold is met."""
        async with self._lock:
            window = self._targets.setdefault(event.target_key, _TargetWindow())
            now = self._now()
            if window.cooldown_until and now < window.cooldown_until:
                return False

            window.events.append((now, event))
            cutoff = now - timedelta(seconds=self.config.window_seconds)
            while window.events and window.events[0][0] < cutoff:
                window.events.popleft()

            if len(window.events) < self.config.min_events:
                return False

            batch = [item[1] for item in window.events]
            window.events.clear()
            if self.config.cooldown_seconds > 0:
                window.cooldown_until = now + timedelta(seconds=self.config.cooldown_seconds)

        logger.info(
            "Trigger fired for %s with %d event(s) in %.1fs window",
            event.target_key,
            len(batch),
            self.config.window_seconds,
        )
        result = self.on_trigger(event.target_key, batch)
        if inspect.isawaitable(result):
            await result
        return True
