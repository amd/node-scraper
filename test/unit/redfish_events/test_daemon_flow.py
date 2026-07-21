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
import asyncio
import json
from datetime import UTC, datetime, timedelta

import pytest

from nodescraper.redfish_events.daemon_config import DaemonConfig, load_daemon_config
from nodescraper.redfish_events.models import EventSource, RedfishEvent
from nodescraper.redfish_events.trigger_engine import TriggerConfig, TriggerEngine


def _event(target_key: str = "bmc-1", message: str = "evt") -> RedfishEvent:
    return RedfishEvent(
        target_key=target_key,
        target_name="node-a",
        target_host="10.0.0.1",
        severity="Warning",
        message=message,
        event_type="Alert",
        received_at=datetime.now(UTC),
        source=EventSource.SSE,
    )


def test_trigger_engine_fires_after_min_events_in_window():
    fired: list[tuple[str, list[RedfishEvent]]] = []
    times = [datetime(2026, 1, 1, tzinfo=UTC)]

    def clock_fn() -> datetime:
        return times[0]

    async def on_trigger(target_key: str, events: list[RedfishEvent]) -> None:
        fired.append((target_key, list(events)))

    engine = TriggerEngine(
        TriggerConfig(min_events=2, window_seconds=10, cooldown_seconds=0),
        on_trigger,
        clock_fn=clock_fn,
    )

    async def _run() -> None:
        assert await engine.handle_event(_event(message="a")) is False
        times[0] += timedelta(seconds=1)
        assert await engine.handle_event(_event(message="b")) is True

    asyncio.run(_run())
    assert len(fired) == 1
    assert fired[0][0] == "bmc-1"
    assert [event.message for event in fired[0][1]] == ["a", "b"]


def test_trigger_engine_respects_cooldown():
    fired: list[str] = []
    times = [datetime(2026, 1, 1, tzinfo=UTC)]

    def clock_fn() -> datetime:
        return times[0]

    async def on_trigger(target_key: str, events: list[RedfishEvent]) -> None:
        fired.append(target_key)

    engine = TriggerEngine(
        TriggerConfig(min_events=1, window_seconds=10, cooldown_seconds=30),
        on_trigger,
        clock_fn=clock_fn,
    )

    async def _run() -> None:
        assert await engine.handle_event(_event()) is True
        times[0] += timedelta(seconds=5)
        assert await engine.handle_event(_event()) is False
        times[0] += timedelta(seconds=30)
        assert await engine.handle_event(_event()) is True

    asyncio.run(_run())
    assert fired == ["bmc-1", "bmc-1"]


def test_load_daemon_config_example(tmp_path):
    payload = {
        "targets": [
            {
                "target_key": "node-a",
                "name": "Node A",
                "host": "10.0.0.1",
                "username": "root",
                "password": "secret",
            }
        ],
        "analysis": {
            "hub_python_module": "hub.mod",
            "afid_sag_path": "/tmp/AFID_SAG.json",
        },
    }
    path = tmp_path / "daemon.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    config = load_daemon_config(path)
    assert isinstance(config, DaemonConfig)
    assert config.targets[0].target_key == "node-a"
    assert config.trigger.min_events == 3


def test_daemon_config_requires_targets():
    with pytest.raises(ValueError, match="At least one target"):
        DaemonConfig.model_validate(
            {
                "targets": [],
                "analysis": {
                    "hub_python_module": "hub.mod",
                    "afid_sag_path": "/tmp/AFID_SAG.json",
                },
            }
        )
