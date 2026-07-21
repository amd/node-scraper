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
"""Continuous Redfish event ingest for node-scraper background services.

This package is separate from on-demand CLI plugin runs. It provides SSE and
webhook-based event subscriptions, baseline log pulls, a trigger engine, and
``node-scraper daemon`` for long-running serviceability monitoring.

Install the optional dependency: pip install amd-node-scraper[events]
"""
from __future__ import annotations

import importlib
from typing import Any

from .config import EventStreamConfig, EventTargetConfig
from .daemon_config import DaemonConfig, HttpServerConfig, load_daemon_config
from .models import (
    EventCallback,
    EventSource,
    RedfishEvent,
    SubscriptionState,
    TransportMode,
)
from .parsing import normalize_severity, parse_redfish_timestamp, severity_allowed
from .se_bridge import redfish_event_to_log_member, redfish_events_to_log_members
from .trigger_engine import TriggerConfig, TriggerEngine

_LAZY_EXPORTS: dict[str, tuple[str, str]] = {
    "AsyncRedfishClient": (".client", "AsyncRedfishClient"),
    "SSECapabilityResult": (".sse_capability", "SSECapabilityResult"),
    "SSESupport": (".sse_capability", "SSESupport"),
    "SseEventSubscriber": (".sse_subscriber", "SseEventSubscriber"),
    "SubscriberManager": (".subscriber_manager", "SubscriberManager"),
    "WebhookEventSubscriber": (".webhook_subscriber", "WebhookEventSubscriber"),
    "WebhookSubscriptionResult": (".webhook_subscriber", "WebhookSubscriptionResult"),
    "check_sse_capability": (".sse_capability", "check_sse_capability"),
    "pull_baseline_events": (".log_baseline", "pull_baseline_events"),
}

__all__ = [
    "AsyncRedfishClient",
    "DaemonConfig",
    "EventCallback",
    "EventSource",
    "EventStreamConfig",
    "EventTargetConfig",
    "HttpServerConfig",
    "RedfishEvent",
    "SSECapabilityResult",
    "SSESupport",
    "SseEventSubscriber",
    "SubscriberManager",
    "SubscriptionState",
    "TransportMode",
    "TriggerConfig",
    "TriggerEngine",
    "WebhookEventSubscriber",
    "WebhookSubscriptionResult",
    "check_sse_capability",
    "load_daemon_config",
    "normalize_severity",
    "parse_redfish_timestamp",
    "pull_baseline_events",
    "redfish_event_to_log_member",
    "redfish_events_to_log_members",
    "severity_allowed",
]


def __getattr__(name: str) -> Any:
    if name not in _LAZY_EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr_name = _LAZY_EXPORTS[name]
    module = importlib.import_module(module_name, __name__)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value
