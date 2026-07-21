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
"""SSE alert subscriber for a single Redfish target (adapted from Gyanam)."""
from __future__ import annotations

import asyncio
import json
import logging
import random
from collections.abc import Callable
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Optional

import httpx

from .models import EventSource, RedfishEvent, SubscriptionState
from .parsing import normalize_severity, parse_redfish_timestamp, severity_allowed

logger = logging.getLogger(__name__)

SSE_READ_TIMEOUT_SECONDS = 300.0
EventHandler = Callable[[RedfishEvent], None]


class ErrorCategory(str, Enum):
    PERMANENT = "permanent"
    TRANSIENT = "transient"


class SseEventSubscriber:
    """Maintain one long-lived Redfish EventService SSE stream."""

    def __init__(
        self,
        *,
        target_key: str,
        target_name: str,
        target_host: str,
        base_url: str,
        username: str,
        password: str,
        sse_endpoint: str = "/redfish/v1/EventService/SSE",
        verify_ssl: bool = False,
        callback: Optional[EventHandler] = None,
        reconnect_delay: int = 30,
        max_retry_duration_hours: float = 24,
        cooldown_duration_hours: float = 6,
        degraded_threshold_hours: float = 1,
        event_types: Optional[list[str]] = None,
        severities: Optional[list[str]] = None,
    ) -> None:
        self.target_key = target_key
        self.target_name = target_name
        self.target_host = target_host
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.sse_endpoint = sse_endpoint
        self.verify_ssl = verify_ssl
        self.callback = callback
        self.reconnect_delay = reconnect_delay
        self.max_retry_duration_hours = max_retry_duration_hours
        self.cooldown_duration_hours = cooldown_duration_hours
        self.degraded_threshold_hours = degraded_threshold_hours
        self.event_types = event_types or ["Alert", "StatusChange"]
        self.severities = severities or ["Warning", "Critical"]

        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._consecutive_failures = 0
        self._last_event_time: Optional[datetime] = None
        self._first_failure_time: Optional[datetime] = None
        self._cooldown_start_time: Optional[datetime] = None
        self._state = SubscriptionState.STOPPED
        self._failure_reason: Optional[str] = None
        self._next_retry_time: Optional[datetime] = None

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._state = SubscriptionState.RECONNECTING
        self._task = asyncio.create_task(self._subscribe_loop())
        logger.info("Started SSE event subscription for %s", self.target_name)

    async def stop(self) -> None:
        self._running = False
        self._state = SubscriptionState.STOPPED
        if self._task:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        logger.info("Stopped SSE event subscription for %s", self.target_name)

    async def _subscribe_loop(self) -> None:
        while self._running:
            try:
                if self._cooldown_start_time:
                    elapsed_hours = (
                        datetime.now(UTC) - self._cooldown_start_time
                    ).total_seconds() / 3600
                    if elapsed_hours < self.cooldown_duration_hours:
                        self._state = SubscriptionState.ON_COOLDOWN
                        await asyncio.sleep(60)
                        continue
                    self._cooldown_start_time = None
                    self._first_failure_time = None
                    self._consecutive_failures = 0
                    self._state = SubscriptionState.RECONNECTING

                await self._connect_and_listen()
            except asyncio.CancelledError:
                break
            except Exception as exc:  # noqa: BLE001
                category, reason = self._classify_error(exc)
                if self._consecutive_failures == 0:
                    self._first_failure_time = datetime.now(UTC)
                self._consecutive_failures += 1
                self._failure_reason = reason

                if category == ErrorCategory.PERMANENT:
                    logger.warning(
                        "Permanent SSE error for %s: %s",
                        self.target_name,
                        reason,
                    )
                    self._state = SubscriptionState.FAILED_PERMANENT
                    self._running = False
                    break

                if self._first_failure_time:
                    elapsed_hours = (
                        datetime.now(UTC) - self._first_failure_time
                    ).total_seconds() / 3600
                    if elapsed_hours >= self.max_retry_duration_hours:
                        self._cooldown_start_time = datetime.now(UTC)
                        self._state = SubscriptionState.ON_COOLDOWN
                        continue
                    if elapsed_hours >= self.degraded_threshold_hours:
                        self._state = SubscriptionState.DEGRADED
                    else:
                        self._state = SubscriptionState.RECONNECTING

                delay = self._calculate_backoff_delay()
                self._next_retry_time = datetime.now(UTC) + timedelta(seconds=delay)
                await asyncio.sleep(delay)

    async def _connect_and_listen(self) -> None:
        url = f"{self.base_url}{self.sse_endpoint}"
        auth = httpx.BasicAuth(self.username, self.password)
        timeout = httpx.Timeout(30.0, read=SSE_READ_TIMEOUT_SECONDS)

        async with (
            httpx.AsyncClient(
                auth=auth,
                verify=self.verify_ssl,
                timeout=timeout,
                follow_redirects=True,
            ) as client,
            client.stream("GET", url) as response,
        ):
            if response.status_code != 200:
                preview = ""
                try:
                    preview = (await response.aread())[:200].decode("utf-8", errors="ignore")
                except Exception:  # noqa: BLE001
                    pass
                raise RuntimeError(f"SSE connection failed: HTTP {response.status_code} {preview}")

            self._consecutive_failures = 0
            self._first_failure_time = None
            self._failure_reason = None
            self._next_retry_time = None
            self._state = SubscriptionState.CONNECTED

            connect_time = datetime.now(UTC)
            event_count = 0
            data_buffer: list[str] = []

            def _dispatch() -> None:
                nonlocal event_count
                if not data_buffer:
                    return
                payload = "\n".join(data_buffer)
                data_buffer.clear()
                if not payload.strip():
                    return
                event_count += 1
                try:
                    self._process_event_data(payload)
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "Failed to process SSE event from %s: %s",
                        self.target_name,
                        exc,
                    )

            async for line in response.aiter_lines():
                if not self._running:
                    break
                line = line.rstrip("\r\n")
                if line == "":
                    _dispatch()
                    continue
                if line.startswith(":"):
                    connect_time = datetime.now(UTC)
                    continue
                if ":" in line:
                    field, _, value = line.partition(":")
                    if value.startswith(" "):
                        value = value[1:]
                else:
                    field, value = line, ""
                if field == "data":
                    data_buffer.append(value)

            _dispatch()

            elapsed = (datetime.now(UTC) - connect_time).total_seconds()
            if elapsed < 30.0 and event_count == 0:
                raise RuntimeError(f"SSE stream closed after {elapsed:.1f}s without sending events")

    def _process_event_data(self, data_str: str) -> None:
        data = json.loads(data_str)
        for event in data.get("Events", []):
            if not isinstance(event, dict):
                continue
            event_type = event.get("EventType") or ""
            severity, sev_present = normalize_severity(event)
            if event_type and self.event_types and event_type not in self.event_types:
                continue
            if not severity_allowed(severity, sev_present, self.severities):
                continue
            if not event_type:
                event_type = "Alert"

            origin = event.get("OriginOfCondition", {})
            origin_uri = None
            if isinstance(origin, dict):
                origin_uri = origin.get("@odata.id")
            elif isinstance(origin, str):
                origin_uri = origin

            redfish_event = RedfishEvent(
                target_key=self.target_key,
                target_name=self.target_name,
                target_host=self.target_host,
                severity=severity,
                message=event.get("Message", ""),
                message_id=event.get("MessageId"),
                event_type=event_type,
                origin_of_condition=origin_uri,
                event_timestamp=parse_redfish_timestamp(event.get("EventTimestamp")),
                received_at=datetime.now(UTC),
                source=EventSource.SSE,
                raw=dict(event),
            )
            self._last_event_time = datetime.now(UTC)
            if self.callback:
                self.callback(redfish_event)

    def _classify_error(self, error: Exception) -> tuple[ErrorCategory, str]:
        error_str = str(error).lower()
        if isinstance(error, httpx.HTTPStatusError):
            status = error.response.status_code
            if status in (401, 403, 404, 405, 501):
                return ErrorCategory.PERMANENT, f"HTTP {status}"
        if isinstance(error, RuntimeError) and "http" in error_str:
            for code in (401, 403, 404, 405, 501):
                if f"http {code}" in error_str:
                    return ErrorCategory.PERMANENT, f"HTTP {code}"
        if "closed after" in error_str and "without sending events" in error_str:
            return ErrorCategory.PERMANENT, "Invalid SSE endpoint"
        if isinstance(error, httpx.TimeoutException | asyncio.TimeoutError):
            return ErrorCategory.TRANSIENT, "Connection timeout"
        if isinstance(error, httpx.ConnectError | OSError):
            return ErrorCategory.TRANSIENT, "Network connection error"
        return ErrorCategory.TRANSIENT, f"{type(error).__name__}: {error}"

    def _calculate_backoff_delay(self) -> int:
        delays = [30, 60, 120, 300, 600, 1800, 3600, 7200]
        idx = min(max(self._consecutive_failures - 1, 0), len(delays) - 1)
        base = delays[idx]
        return int(base * random.uniform(0.8, 1.2))

    @property
    def state(self) -> SubscriptionState:
        return self._state

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def last_event_time(self) -> Optional[datetime]:
        return self._last_event_time

    @property
    def failure_reason(self) -> Optional[str]:
        return self._failure_reason
