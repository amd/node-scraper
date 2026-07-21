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
"""Minimal async Redfish GET client for event ingest follow-up requests."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import httpx


@dataclass
class RedfishGetResponse:
    """Result of an async Redfish GET."""

    ok: bool
    status_code: int
    data: Optional[dict[str, Any]] = None
    content: bytes = b""
    error: Optional[str] = None


class AsyncRedfishClient:
    """Small httpx wrapper for Redfish JSON and binary GETs."""

    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        *,
        verify_ssl: bool = False,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._auth = httpx.BasicAuth(username, password)
        self._verify_ssl = verify_ssl
        self._timeout = timeout_seconds

    def _abs_url(self, path: str) -> str:
        if path.startswith("http://") or path.startswith("https://"):
            return path
        return f"{self.base_url}/{path.lstrip('/')}"

    async def get_json(self, path: str) -> RedfishGetResponse:
        try:
            async with httpx.AsyncClient(
                auth=self._auth,
                verify=self._verify_ssl,
                timeout=self._timeout,
                follow_redirects=True,
            ) as client:
                response = await client.get(self._abs_url(path))
        except Exception as exc:  # noqa: BLE001
            return RedfishGetResponse(ok=False, status_code=0, error=str(exc))
        if response.status_code != 200:
            return RedfishGetResponse(
                ok=False,
                status_code=response.status_code,
                error=response.text[:500],
            )
        try:
            return RedfishGetResponse(ok=True, status_code=200, data=response.json())
        except Exception as exc:  # noqa: BLE001
            return RedfishGetResponse(ok=False, status_code=200, error=str(exc))

    async def get_bytes(self, path: str) -> RedfishGetResponse:
        try:
            async with httpx.AsyncClient(
                auth=self._auth,
                verify=self._verify_ssl,
                timeout=self._timeout,
                follow_redirects=True,
            ) as client:
                response = await client.get(self._abs_url(path))
        except Exception as exc:  # noqa: BLE001
            return RedfishGetResponse(ok=False, status_code=0, error=str(exc))
        if response.status_code != 200:
            return RedfishGetResponse(
                ok=False,
                status_code=response.status_code,
                error=response.text[:500],
            )
        return RedfishGetResponse(ok=True, status_code=200, content=response.content)
