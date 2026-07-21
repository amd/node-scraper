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
"""Data models for continuous Redfish event ingest."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional, Union

EventCallback = Callable[["RedfishEvent"], Union[None, Awaitable[None]]]


class EventSource(str, Enum):
    """How an event entered the ingest pipeline."""

    SSE = "sse"
    WEBHOOK = "webhook"
    BASELINE = "baseline"


class TransportMode(str, Enum):
    """Preferred Redfish event transport for a target."""

    AUTO = "auto"
    SSE = "sse"
    WEBHOOK = "webhook"


class SubscriptionState(str, Enum):
    """Connection state for a target event subscription."""

    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    DEGRADED = "degraded"
    ON_COOLDOWN = "on_cooldown"
    FAILED_PERMANENT = "failed_permanent"
    STOPPED = "stopped"


@dataclass
class RedfishEvent:
    """Normalized Redfish alert or log entry for downstream consumers."""

    target_key: str
    target_name: str
    target_host: str
    severity: str
    message: str
    event_type: str
    received_at: datetime
    source: EventSource
    message_id: Optional[str] = None
    origin_of_condition: Optional[str] = None
    event_timestamp: Optional[datetime] = None
    source_id: Optional[str] = None
    raw: Optional[dict[str, Any]] = field(default_factory=dict)

    def dedupe_key(self) -> str:
        """Return a stable key for in-memory deduplication."""
        if self.source_id:
            return self.source_id
        parts = (
            self.target_key,
            self.message_id or "",
            self.event_type,
            self.message,
            self.event_timestamp.isoformat() if self.event_timestamp else "",
        )
        return "|".join(parts)
