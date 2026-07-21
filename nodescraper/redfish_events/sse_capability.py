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
"""Detect whether a BMC supports Redfish EventService SSE."""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


class SSESupport(str, Enum):
    SUPPORTED = "supported"
    NOT_SUPPORTED = "not_supported"
    BROKEN = "broken"
    UNKNOWN = "unknown"


@dataclass
class SSECapabilityResult:
    support: SSESupport
    reason: str
    event_service_enabled: bool = False
    sse_endpoint: Optional[str] = None
    test_duration_ms: float = 0.0


async def check_sse_capability(
    base_url: str,
    username: str,
    password: str,
    verify_ssl: bool = False,
    test_duration_seconds: float = 5.0,
) -> SSECapabilityResult:
    start = time.time()
    try:
        async with httpx.AsyncClient(
            auth=httpx.BasicAuth(username, password),
            verify=verify_ssl,
            timeout=10.0,
        ) as client:
            response = await client.get(f"{base_url.rstrip('/')}/redfish/v1/EventService")
            if response.status_code == 404:
                return SSECapabilityResult(
                    support=SSESupport.NOT_SUPPORTED,
                    reason="EventService not found (404)",
                    test_duration_ms=(time.time() - start) * 1000,
                )
            if response.status_code != 200:
                return SSECapabilityResult(
                    support=SSESupport.UNKNOWN,
                    reason=f"EventService returned HTTP {response.status_code}",
                    test_duration_ms=(time.time() - start) * 1000,
                )
            event_service = response.json()
            enabled = bool(event_service.get("ServiceEnabled", False))
            sse_uri = event_service.get("ServerSentEventUri")
            if not sse_uri:
                return SSECapabilityResult(
                    support=SSESupport.NOT_SUPPORTED,
                    reason="ServerSentEventUri not advertised",
                    event_service_enabled=enabled,
                    test_duration_ms=(time.time() - start) * 1000,
                )
            sse_url = sse_uri if sse_uri.startswith("http") else f"{base_url.rstrip('/')}{sse_uri}"
            result = await _test_sse_endpoint(
                sse_url,
                username,
                password,
                verify_ssl,
                test_duration_seconds,
            )
            result.event_service_enabled = enabled
            result.sse_endpoint = sse_uri
            result.test_duration_ms = (time.time() - start) * 1000
            return result
    except httpx.TimeoutException:
        return SSECapabilityResult(
            support=SSESupport.UNKNOWN,
            reason="Timeout checking EventService",
            test_duration_ms=(time.time() - start) * 1000,
        )
    except Exception as exc:  # noqa: BLE001
        return SSECapabilityResult(
            support=SSESupport.UNKNOWN,
            reason=f"{type(exc).__name__}: {exc}",
            test_duration_ms=(time.time() - start) * 1000,
        )


async def _test_sse_endpoint(
    sse_url: str,
    username: str,
    password: str,
    verify_ssl: bool,
    test_duration: float,
) -> SSECapabilityResult:
    try:
        timeout = httpx.Timeout(10.0, read=test_duration + 2.0)
        async with (
            httpx.AsyncClient(
                auth=httpx.BasicAuth(username, password),
                verify=verify_ssl,
                timeout=timeout,
            ) as client,
            client.stream("GET", sse_url) as response,
        ):
            if response.status_code in (404, 501):
                return SSECapabilityResult(
                    support=SSESupport.NOT_SUPPORTED,
                    reason=f"SSE endpoint HTTP {response.status_code}",
                )
            if response.status_code != 200:
                return SSECapabilityResult(
                    support=SSESupport.BROKEN,
                    reason=f"SSE endpoint HTTP {response.status_code}",
                )
            content_type = response.headers.get("content-type", "")
            if "text/event-stream" not in content_type.lower():
                return SSECapabilityResult(
                    support=SSESupport.BROKEN,
                    reason=f"Unexpected content-type: {content_type}",
                )

            lines_received = 0
            keepalives = 0
            events = 0

            async def _read_lines() -> None:
                nonlocal lines_received, keepalives, events
                async for line in response.aiter_lines():
                    lines_received += 1
                    stripped = line.strip()
                    if not stripped:
                        continue
                    if stripped.startswith(":"):
                        keepalives += 1
                    elif stripped.startswith("data:"):
                        events += 1

            try:
                await asyncio.wait_for(_read_lines(), timeout=test_duration)
            except asyncio.TimeoutError:
                pass

            if lines_received == 0:
                return SSECapabilityResult(
                    support=SSESupport.BROKEN,
                    reason="SSE stream opened but no data received",
                )
            if keepalives or events:
                return SSECapabilityResult(
                    support=SSESupport.SUPPORTED,
                    reason=(
                        f"SSE working ({events} events, {keepalives} keep-alives "
                        f"in {test_duration}s test)"
                    ),
                )
            return SSECapabilityResult(
                support=SSESupport.BROKEN,
                reason=f"SSE active but invalid format ({lines_received} lines)",
            )
    except httpx.ConnectError as exc:
        return SSECapabilityResult(
            support=SSESupport.UNKNOWN,
            reason=f"Cannot connect: {exc}",
        )
    except httpx.TimeoutException:
        return SSECapabilityResult(
            support=SSESupport.UNKNOWN,
            reason="Timeout connecting to SSE endpoint",
        )
    except Exception as exc:  # noqa: BLE001
        return SSECapabilityResult(
            support=SSESupport.BROKEN,
            reason=f"{type(exc).__name__}: {exc}",
        )
