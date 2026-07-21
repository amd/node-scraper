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
"""Configuration models for Redfish event subscriptions."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, model_validator

from .models import TransportMode

DEFAULT_SSE_ENDPOINT = "/redfish/v1/EventService/SSE"


class EventTargetConfig(BaseModel):
    """One BMC target for continuous event ingest."""

    target_key: str = Field(..., min_length=1, description="Stable unique id for this target")
    name: str = Field(..., min_length=1, description="Display name")
    host: str = Field(..., min_length=1, description="BMC hostname or IP")
    username: str
    password: str
    base_url: Optional[str] = Field(
        default=None,
        description="Redfish base URL; defaults to https://<host>",
    )
    verify_ssl: bool = False
    sse_endpoint: str = DEFAULT_SSE_ENDPOINT
    transport: TransportMode = TransportMode.AUTO
    webhook_url: Optional[str] = Field(
        default=None,
        description="Collector webhook URL when transport is webhook or auto fallback",
    )

    def resolved_base_url(self) -> str:
        if self.base_url:
            return self.base_url.rstrip("/")
        return f"https://{self.host}"


class EventStreamConfig(BaseModel):
    """Global settings for SubscriberManager."""

    event_types: list[str] = Field(default_factory=lambda: ["Alert", "StatusChange"])
    severities: list[str] = Field(default_factory=lambda: ["Warning", "Critical"])
    reconnect_delay_seconds: int = 30
    max_retry_duration_hours: float = 24.0
    cooldown_duration_hours: float = 6.0
    degraded_threshold_hours: float = 1.0
    baseline_pull_enabled: bool = True
    baseline_max_entries_per_log: int = 200
    baseline_repull_interval_minutes: int = 60
    enable_webhook_fallback: bool = True
    allow_loopback_webhook: bool = False
    dedupe_events: bool = True
    max_dedupe_entries: int = 10000

    @model_validator(mode="after")
    def _validate_lists(self) -> EventStreamConfig:
        if not self.event_types:
            raise ValueError("event_types must not be empty")
        if not self.severities:
            raise ValueError("severities must not be empty")
        return self
