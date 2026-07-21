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
"""Webhook-based Redfish event subscriptions."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import Optional

import httpx

from .models import EventSource, RedfishEvent
from .parsing import normalize_severity, parse_redfish_timestamp, severity_allowed

logger = logging.getLogger(__name__)


class WebhookFailureType(str, Enum):
    TEMPORARY = "temporary"
    PERMANENT = "permanent"


@dataclass
class WebhookSubscriptionResult:
    success: bool
    failure_type: Optional[WebhookFailureType] = None
    error_message: Optional[str] = None


class WebhookEventSubscriber:
    """Create and parse Redfish webhook subscriptions for one target."""

    def __init__(
        self,
        *,
        target_key: str,
        target_name: str,
        target_host: str,
        base_url: str,
        username: str,
        password: str,
        webhook_url: str,
        verify_ssl: bool = False,
        event_types: Optional[list[str]] = None,
        severities: Optional[list[str]] = None,
    ) -> None:
        self.target_key = target_key
        self.target_name = target_name
        self.target_host = target_host
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.webhook_url = webhook_url
        self.verify_ssl = verify_ssl
        self.event_types = event_types or ["Alert", "StatusChange"]
        self.severities = severities or ["Warning", "Critical"]
        self._subscription_id: Optional[str] = None
        self._subscription_url: Optional[str] = None

    async def create_subscription(self) -> WebhookSubscriptionResult:
        payload = {
            "Destination": self.webhook_url,
            "Protocol": "Redfish",
            "EventTypes": self.event_types,
            "Context": self.target_key,
        }
        try:
            async with httpx.AsyncClient(
                auth=httpx.BasicAuth(self.username, self.password),
                verify=self.verify_ssl,
                timeout=30.0,
            ) as client:
                response = await client.post(
                    f"{self.base_url}/redfish/v1/EventService/Subscriptions",
                    json=payload,
                )
                if response.status_code in (200, 201):
                    data = response.json()
                    self._subscription_id = data.get("Id")
                    location = response.headers.get("Location")
                    if location:
                        self._subscription_url = location
                    elif self._subscription_id:
                        self._subscription_url = (
                            f"{self.base_url}/redfish/v1/EventService/Subscriptions/"
                            f"{self._subscription_id}"
                        )
                    return WebhookSubscriptionResult(success=True)
                if response.status_code == 409:
                    await self._find_existing_subscription()
                    if self._subscription_id:
                        return WebhookSubscriptionResult(success=True)
                if response.status_code in (400, 405, 501):
                    return WebhookSubscriptionResult(
                        success=False,
                        failure_type=WebhookFailureType.PERMANENT,
                        error_message=response.text[:200],
                    )
                return WebhookSubscriptionResult(
                    success=False,
                    failure_type=WebhookFailureType.TEMPORARY,
                    error_message=f"HTTP {response.status_code}",
                )
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            return WebhookSubscriptionResult(
                success=False,
                failure_type=WebhookFailureType.TEMPORARY,
                error_message=str(exc),
            )

    async def delete_subscription(self) -> bool:
        if not self._subscription_url:
            return False
        try:
            async with httpx.AsyncClient(
                auth=httpx.BasicAuth(self.username, self.password),
                verify=self.verify_ssl,
                timeout=10.0,
            ) as client:
                response = await client.delete(self._subscription_url)
                if response.status_code in (200, 204, 404):
                    self._subscription_id = None
                    self._subscription_url = None
                    return True
        except Exception as exc:  # noqa: BLE001
            logger.debug("Webhook delete failed for %s: %s", self.target_name, exc)
        return False

    async def _find_existing_subscription(self) -> None:
        try:
            async with httpx.AsyncClient(
                auth=httpx.BasicAuth(self.username, self.password),
                verify=self.verify_ssl,
                timeout=10.0,
            ) as client:
                response = await client.get(
                    f"{self.base_url}/redfish/v1/EventService/Subscriptions"
                )
                if response.status_code != 200:
                    return
                for member in response.json().get("Members", []):
                    ref = member.get("@odata.id")
                    if not ref:
                        continue
                    detail = await client.get(f"{self.base_url}{ref}")
                    if detail.status_code != 200:
                        continue
                    data = detail.json()
                    if data.get("Destination") == self.webhook_url:
                        self._subscription_id = ref.rstrip("/").split("/")[-1]
                        self._subscription_url = f"{self.base_url}{ref}"
                        return
        except Exception as exc:  # noqa: BLE001
            logger.debug("Webhook lookup failed for %s: %s", self.target_name, exc)

    def parse_webhook_payload(self, event_data: dict) -> list[RedfishEvent]:
        events = event_data.get("Events")
        if not isinstance(events, list):
            events = (
                [event_data] if (event_data.get("MessageId") or event_data.get("Message")) else []
            )
        parsed: list[RedfishEvent] = []
        for event in events:
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
            origin_uri = origin.get("@odata.id") if isinstance(origin, dict) else origin
            parsed.append(
                RedfishEvent(
                    target_key=self.target_key,
                    target_name=self.target_name,
                    target_host=self.target_host,
                    severity=severity,
                    message=event.get("Message", ""),
                    message_id=event.get("MessageId"),
                    event_type=event_type,
                    origin_of_condition=origin_uri if isinstance(origin_uri, str) else None,
                    event_timestamp=parse_redfish_timestamp(event.get("EventTimestamp")),
                    received_at=datetime.now(UTC),
                    source=EventSource.WEBHOOK,
                    raw=dict(event),
                )
            )
        return parsed

    @property
    def is_subscribed(self) -> bool:
        return self._subscription_id is not None
