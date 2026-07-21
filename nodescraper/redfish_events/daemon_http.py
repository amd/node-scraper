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
"""Minimal asyncio HTTP server for webhook ingest and live recommendations."""
from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from typing import Any, Optional

from .daemon_config import HttpServerConfig
from .subscriber_manager import SubscriberManager

logger = logging.getLogger(__name__)


class DaemonHttpServer:
    """Serve webhook POST endpoints and JSON recommendation snapshots."""

    def __init__(
        self,
        manager: SubscriberManager,
        recommendations: dict[str, dict[str, Any]],
        config: HttpServerConfig,
    ) -> None:
        self._manager = manager
        self._recommendations = recommendations
        self._config = config
        self._server: Optional[asyncio.AbstractServer] = None

    async def start(self) -> None:
        """Bind and start accepting HTTP connections."""
        self._server = await asyncio.start_server(
            self._handle_client,
            host=self._config.host,
            port=self._config.port,
        )
        logger.info(
            "Daemon HTTP listening on http://%s:%d",
            self._config.host,
            self._config.port,
        )

    async def stop(self) -> None:
        """Stop the HTTP server."""
        if self._server is None:
            return
        self._server.close()
        await self._server.wait_closed()
        self._server = None

    async def _handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        try:
            request_line = (await reader.readline()).decode("utf-8", errors="replace").strip()
            if not request_line:
                return
            parts = request_line.split()
            if len(parts) < 2:
                await self._write_response(writer, 400, {"error": "bad request line"})
                return
            method = parts[0].upper()
            path = parts[1].split("?", 1)[0]

            headers: dict[str, str] = {}
            while True:
                line = (await reader.readline()).decode("utf-8", errors="replace").strip()
                if not line:
                    break
                if ":" in line:
                    key, value = line.split(":", 1)
                    headers[key.strip().lower()] = value.strip()

            body = b""
            content_length = int(headers.get("content-length", "0") or "0")
            if content_length > 0:
                body = await reader.readexactly(content_length)

            if method == "GET":
                await self._handle_get(writer, path)
                return
            if method == "POST":
                await self._handle_post(writer, path, body)
                return
            await self._write_response(writer, 405, {"error": "method not allowed"})
        except asyncio.IncompleteReadError:
            return
        except Exception as exc:  # noqa: BLE001
            logger.warning("HTTP handler error: %s", exc)
            await self._write_response(writer, 500, {"error": "internal error"})
        finally:
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()

    async def _handle_get(self, writer: asyncio.StreamWriter, path: str) -> None:
        if path == self._config.status_path:
            targets: dict[str, dict[str, Any]] = {}
            for key in self._manager.target_keys():
                state = self._manager.subscription_state(key)
                targets[key] = {
                    "transport": self._manager.transport_for(key),
                    "subscription_state": state.value if state is not None else None,
                }
            payload = {
                "status": "ok",
                "targets": targets,
            }
            await self._write_response(writer, 200, payload)
            return

        if path == self._config.recommendations_path:
            await self._write_response(writer, 200, self._recommendations)
            return

        prefix = self._config.recommendations_path.rstrip("/") + "/"
        if path.startswith(prefix):
            target_key = path[len(prefix) :]
            snapshot = self._recommendations.get(target_key)
            if snapshot is None:
                await self._write_response(writer, 404, {"error": f"unknown target {target_key}"})
                return
            await self._write_response(writer, 200, snapshot)
            return

        await self._write_response(writer, 404, {"error": "not found"})

    async def _handle_post(
        self,
        writer: asyncio.StreamWriter,
        path: str,
        body: bytes,
    ) -> None:
        prefix = self._config.webhook_path_prefix.rstrip("/") + "/"
        if not path.startswith(prefix):
            await self._write_response(writer, 404, {"error": "not found"})
            return
        target_key = path[len(prefix) :]
        if not target_key:
            await self._write_response(writer, 400, {"error": "missing target_key in path"})
            return
        try:
            payload = json.loads(body.decode("utf-8") if body else "{}")
        except json.JSONDecodeError:
            await self._write_response(writer, 400, {"error": "invalid JSON body"})
            return
        if not isinstance(payload, dict):
            await self._write_response(writer, 400, {"error": "JSON body must be an object"})
            return
        emitted = await self._manager.handle_webhook_payload(target_key, payload)
        await self._write_response(writer, 200, {"accepted": True, "events_emitted": emitted})

    async def _write_response(
        self,
        writer: asyncio.StreamWriter,
        status: int,
        payload: dict[str, Any],
    ) -> None:
        body = json.dumps(payload).encode("utf-8")
        reason = {
            200: "OK",
            400: "Bad Request",
            404: "Not Found",
            405: "Method Not Allowed",
            500: "Internal Server Error",
        }.get(status, "OK")
        header = (
            f"HTTP/1.1 {status} {reason}\r\n"
            "Content-Type: application/json\r\n"
            f"Content-Length: {len(body)}\r\n"
            "Connection: close\r\n"
            "\r\n"
        ).encode("utf-8")
        writer.write(header + body)
        await writer.drain()
