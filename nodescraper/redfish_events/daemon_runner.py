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
"""Long-running Redfish event daemon orchestration."""
from __future__ import annotations

import asyncio
import logging
import signal
from datetime import UTC, datetime
from typing import Any, Optional

from nodescraper.plugins.serviceability.analysis_window import (
    analyze_serviceability_window,
)
from nodescraper.plugins.serviceability.se_adapter import (
    format_serviceability_solution_lines,
)
from nodescraper.plugins.serviceability.serviceability_data import (
    ServiceabilityDataModel,
)

from .daemon_config import DaemonConfig
from .daemon_http import DaemonHttpServer
from .models import RedfishEvent
from .se_bridge import redfish_events_to_log_members
from .subscriber_manager import SubscriberManager
from .trigger_engine import TriggerEngine

logger = logging.getLogger(__name__)


class EventDaemon:
    """Wire SubscriberManager, trigger engine, analysis, and optional HTTP endpoints."""

    def __init__(self, config: DaemonConfig) -> None:
        self.config = config
        self._recommendations: dict[str, dict[str, Any]] = {}
        self._manager = SubscriberManager(config.stream, self._on_event)
        self._manager.set_targets(config.targets)
        self._trigger = TriggerEngine(config.trigger, self._on_trigger)
        self._http: Optional[DaemonHttpServer] = None
        self._stop_event = asyncio.Event()

    async def run(self) -> None:
        """Start subscriptions and block until SIGINT or SIGTERM."""
        loop = asyncio.get_running_loop()
        try:
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(sig, self._stop_event.set)
        except NotImplementedError:
            signal.signal(signal.SIGINT, lambda *_args: self._stop_event.set())

        if self.config.http.enabled:
            self._http = DaemonHttpServer(self._manager, self._recommendations, self.config.http)
            await self._http.start()

        await self._manager.start()
        logger.info(
            "Redfish event daemon running for %d target(s); Ctrl+C to stop",
            len(self.config.targets),
        )
        await self._stop_event.wait()
        await self.stop()

    async def stop(self) -> None:
        """Stop subscriptions and the HTTP server."""
        await self._manager.stop()
        if self._http is not None:
            await self._http.stop()
            self._http = None
        logger.info("Redfish event daemon stopped")

    async def _on_event(self, event: RedfishEvent) -> None:
        await self._trigger.handle_event(event)

    async def _on_trigger(self, target_key: str, events: list[RedfishEvent]) -> None:
        target_name = events[0].target_name if events else target_key
        rf_members = redfish_events_to_log_members(events)
        bmc_host = events[0].target_host if events else None
        data = ServiceabilityDataModel(rf_events=rf_members, bmc_host=bmc_host)
        parent = f"EventDaemon:{target_key}"
        result = await asyncio.to_thread(
            analyze_serviceability_window,
            data,
            self.config.analysis,
            logger=logger,
            parent=parent,
        )
        snapshot = {
            "target_key": target_key,
            "target_name": target_name,
            "triggered_at": datetime.now(UTC).isoformat(),
            "event_count": len(events),
            "ok": result.ok,
            "message": result.message,
            "afid_events": [event.model_dump(mode="json") for event in result.afid_events],
        }
        if result.serviceability is not None:
            snapshot["serviceability"] = result.serviceability.model_dump(mode="json")
            for line in format_serviceability_solution_lines(result.serviceability):
                logger.info("(%s) %s", parent, line)
        elif result.error:
            logger.error("(%s) analysis failed: %s", parent, result.error)
        else:
            logger.info("(%s) %s", parent, result.message)
        self._recommendations[target_key] = snapshot


def run_event_daemon(config: DaemonConfig) -> None:
    """Run the daemon until interrupted."""
    try:
        import httpx  # noqa: F401
    except ImportError as exc:
        raise RuntimeError(
            "Redfish event daemon requires the optional [events] extra: "
            "pip install amd-node-scraper[events]"
        ) from exc

    daemon = EventDaemon(config)
    asyncio.run(daemon.run())
