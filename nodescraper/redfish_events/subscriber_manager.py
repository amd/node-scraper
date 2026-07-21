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
"""Manage continuous Redfish event subscriptions for multiple BMC targets."""
from __future__ import annotations

import asyncio
import contextlib
import inspect
import logging
from collections import OrderedDict
from ipaddress import ip_address
from typing import Optional
from urllib.parse import urlparse

from .config import EventStreamConfig, EventTargetConfig
from .log_baseline import pull_baseline_events
from .models import EventCallback, RedfishEvent, SubscriptionState, TransportMode
from .sse_capability import SSESupport, check_sse_capability
from .sse_subscriber import SseEventSubscriber
from .webhook_subscriber import WebhookEventSubscriber, WebhookFailureType

logger = logging.getLogger(__name__)


def _webhook_unreachable(url: str) -> tuple[bool, str]:
    try:
        parsed = urlparse(url)
    except Exception as exc:  # noqa: BLE001
        return True, f"unparseable URL: {exc}"
    if not parsed.scheme or not parsed.hostname:
        return True, "missing scheme or host"
    host = parsed.hostname
    if host in {"localhost", "0.0.0.0"}:
        return True, f"host '{host}' is unreachable from a BMC"
    try:
        ip = ip_address(host)
        if ip.is_loopback or ip.is_unspecified:
            return True, f"host '{host}' is loopback/unspecified"
    except ValueError:
        pass
    return False, ""


class SubscriberManager:
    """Start SSE or webhook ingest for configured targets and dispatch events."""

    def __init__(
        self,
        config: EventStreamConfig,
        on_event: EventCallback,
    ) -> None:
        self.config = config
        self.on_event = on_event
        self._targets: dict[str, EventTargetConfig] = {}
        self._sse: dict[str, SseEventSubscriber] = {}
        self._webhooks: dict[str, WebhookEventSubscriber] = {}
        self._transport: dict[str, str] = {}
        self._running = False
        self._baseline_task: Optional[asyncio.Task] = None
        self._dedupe: OrderedDict[str, None] = OrderedDict()

    def set_targets(self, targets: list[EventTargetConfig]) -> None:
        self._targets = {target.target_key: target for target in targets}

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        for target in self._targets.values():
            await self._start_target(target)
        if self.config.baseline_repull_interval_minutes > 0:
            self._baseline_task = asyncio.create_task(self._baseline_repull_loop())
        logger.info("SubscriberManager started for %d target(s)", len(self._targets))

    async def stop(self) -> None:
        self._running = False
        if self._baseline_task:
            self._baseline_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._baseline_task
            self._baseline_task = None
        for key, subscriber in list(self._sse.items()):
            await subscriber.stop()
            del self._sse[key]
        for key, webhook in list(self._webhooks.items()):
            await webhook.delete_subscription()
            del self._webhooks[key]
        self._transport.clear()
        logger.info("SubscriberManager stopped")

    async def handle_webhook_payload(
        self,
        target_key: str,
        payload: dict,
    ) -> int:
        webhook = self._webhooks.get(target_key)
        if webhook is None:
            logger.warning("Webhook payload for unknown target_key=%s", target_key)
            return 0
        emitted = 0
        for event in webhook.parse_webhook_payload(payload):
            if await self._dispatch(event):
                emitted += 1
        return emitted

    def subscription_state(self, target_key: str) -> Optional[SubscriptionState]:
        subscriber = self._sse.get(target_key)
        if subscriber is not None:
            return subscriber.state
        if target_key in self._webhooks:
            return SubscriptionState.CONNECTED
        return None

    def transport_for(self, target_key: str) -> Optional[str]:
        return self._transport.get(target_key)

    def target_keys(self) -> list[str]:
        """Return configured target keys in registration order."""
        return list(self._targets.keys())

    async def _start_target(self, target: EventTargetConfig) -> None:
        if self.config.baseline_pull_enabled:
            await pull_baseline_events(
                target_key=target.target_key,
                target_name=target.name,
                target_host=target.host,
                base_url=target.resolved_base_url(),
                username=target.username,
                password=target.password,
                verify_ssl=target.verify_ssl,
                callback=self._baseline_callback,
                severities=self.config.severities,
                max_entries_per_log=self.config.baseline_max_entries_per_log,
            )

        mode = target.transport
        if mode == TransportMode.AUTO:
            cap = await check_sse_capability(
                target.resolved_base_url(),
                target.username,
                target.password,
                target.verify_ssl,
            )
            if cap.support == SSESupport.SUPPORTED:
                mode = TransportMode.SSE
            elif target.webhook_url and self.config.enable_webhook_fallback:
                mode = TransportMode.WEBHOOK
            else:
                logger.warning(
                    "No supported event transport for %s: %s",
                    target.name,
                    cap.reason,
                )
                return

        if mode == TransportMode.SSE:
            subscriber = SseEventSubscriber(
                target_key=target.target_key,
                target_name=target.name,
                target_host=target.host,
                base_url=target.resolved_base_url(),
                username=target.username,
                password=target.password,
                sse_endpoint=target.sse_endpoint,
                verify_ssl=target.verify_ssl,
                callback=self._sse_callback,
                reconnect_delay=self.config.reconnect_delay_seconds,
                max_retry_duration_hours=self.config.max_retry_duration_hours,
                cooldown_duration_hours=self.config.cooldown_duration_hours,
                degraded_threshold_hours=self.config.degraded_threshold_hours,
                event_types=self.config.event_types,
                severities=self.config.severities,
            )
            self._sse[target.target_key] = subscriber
            self._transport[target.target_key] = "sse"
            await subscriber.start()
            return

        if mode == TransportMode.WEBHOOK:
            if not target.webhook_url:
                logger.error("Target %s requires webhook_url for webhook transport", target.name)
                return
            unreachable, reason = _webhook_unreachable(target.webhook_url)
            if unreachable and not self.config.allow_loopback_webhook:
                logger.error(
                    "Webhook URL for %s is unreachable from BMCs: %s",
                    target.name,
                    reason,
                )
                return
            webhook = WebhookEventSubscriber(
                target_key=target.target_key,
                target_name=target.name,
                target_host=target.host,
                base_url=target.resolved_base_url(),
                username=target.username,
                password=target.password,
                webhook_url=target.webhook_url,
                verify_ssl=target.verify_ssl,
                event_types=self.config.event_types,
                severities=self.config.severities,
            )
            result = await webhook.create_subscription()
            if not result.success:
                level = (
                    logging.ERROR
                    if result.failure_type == WebhookFailureType.PERMANENT
                    else logging.WARNING
                )
                logger.log(
                    level,
                    "Webhook subscription failed for %s: %s",
                    target.name,
                    result.error_message,
                )
                return
            self._webhooks[target.target_key] = webhook
            self._transport[target.target_key] = "webhook"

    def _sse_callback(self, event: RedfishEvent) -> None:
        asyncio.create_task(self._dispatch(event))

    def _baseline_callback(self, event: RedfishEvent) -> None:
        asyncio.create_task(self._dispatch(event))

    async def _dispatch(self, event: RedfishEvent) -> bool:
        if self.config.dedupe_events:
            key = f"{event.target_key}:{event.dedupe_key()}"
            if key in self._dedupe:
                return False
            self._dedupe[key] = None
            while len(self._dedupe) > self.config.max_dedupe_entries:
                self._dedupe.popitem(last=False)

        result = self.on_event(event)
        if inspect.isawaitable(result):
            await result
        return True

    async def _baseline_repull_loop(self) -> None:
        interval = self.config.baseline_repull_interval_minutes * 60
        while self._running:
            try:
                await asyncio.sleep(interval)
                for target in self._targets.values():
                    await pull_baseline_events(
                        target_key=target.target_key,
                        target_name=target.name,
                        target_host=target.host,
                        base_url=target.resolved_base_url(),
                        username=target.username,
                        password=target.password,
                        verify_ssl=target.verify_ssl,
                        callback=self._baseline_callback,
                        severities=self.config.severities,
                        max_entries_per_log=self.config.baseline_max_entries_per_log,
                    )
            except asyncio.CancelledError:
                break
            except Exception as exc:  # noqa: BLE001
                logger.warning("Baseline re-pull loop error: %s", exc)
