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
from typing import cast
from unittest.mock import AsyncMock, MagicMock

from nodescraper.redfish_events.daemon_config import HttpServerConfig
from nodescraper.redfish_events.daemon_http import DaemonHttpServer
from nodescraper.redfish_events.models import SubscriptionState


def test_daemon_http_status_and_webhook_post():
    asyncio.run(_run())


async def _run() -> None:
    manager = MagicMock()
    manager.target_keys.return_value = ["node-a"]
    manager.transport_for.return_value = "webhook"
    manager.subscription_state.return_value = SubscriptionState.CONNECTED
    manager.handle_webhook_payload = AsyncMock(return_value=1)

    recommendations: dict = {}
    server = DaemonHttpServer(
        manager,
        recommendations,
        HttpServerConfig.model_construct(host="127.0.0.1", port=0),
    )
    await server.start()
    assert server._server is not None
    bound_server = cast(asyncio.Server, server._server)
    port = bound_server.sockets[0].getsockname()[1]

    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    writer.write(b"GET /status HTTP/1.1\r\nHost: localhost\r\n\r\n")
    await writer.drain()
    response = await reader.readuntil(b"\r\n\r\n")
    body = await reader.read()
    writer.close()
    await writer.wait_closed()
    assert b"200 OK" in response
    payload = json.loads(body.decode("utf-8"))
    assert payload["status"] == "ok"
    assert "node-a" in payload["targets"]

    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    body_bytes = json.dumps({"Message": "hot", "MessageSeverity": "Critical"}).encode("utf-8")
    request = (
        b"POST /hook/node-a HTTP/1.1\r\n"
        b"Host: localhost\r\n"
        + f"Content-Length: {len(body_bytes)}\r\n\r\n".encode("utf-8")
        + body_bytes
    )
    writer.write(request)
    await writer.drain()
    response = await reader.readuntil(b"\r\n\r\n")
    body = await reader.read()
    writer.close()
    await writer.wait_closed()
    assert b"200 OK" in response
    assert json.loads(body.decode("utf-8"))["events_emitted"] == 1
    manager.handle_webhook_payload.assert_awaited_once()

    await server.stop()
