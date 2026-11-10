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
from __future__ import annotations

from typing import Any

import requests
import urllib3  # type: ignore[import-untyped]

from .oob_rest_params import OobRestConnectionParams


class OobRestConnection:
    """Generic REST transport for an out-of-band controller.

    Owns a ``requests`` session, authenticates once with a username/password POST
    to the configured login endpoint, and issues authenticated JSON requests.
    Controller-specific endpoints and response parsing belong in the caller, not
    here.
    """

    def __init__(self, params: OobRestConnectionParams):
        self._params = params
        scheme = "https" if params.use_https else "http"
        host = str(params.host)
        self._base = f"{scheme}://{host}:{params.port}" if params.port else f"{scheme}://{host}"
        self._session = requests.Session()
        self._session.verify = params.verify_ssl
        if not params.verify_ssl:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        self._authenticated = False

    @property
    def base_url(self) -> str:
        """Return the base URL the connection issues requests against."""
        return self._base

    def authenticate(self) -> None:
        """Authenticate against the controller's login endpoint.

        Idempotent: a no-op once authenticated. Called automatically before any
        request, and also invoked by the connection manager to verify the
        connection on connect.
        """
        if self._authenticated:
            return
        password = (
            self._params.password.get_secret_value() if self._params.password is not None else None
        )
        payload: dict[str, Any] = {
            "username": self._params.username,
            "password": password,
            **self._params.login_payload_extra,
        }
        resp = self._session.post(
            f"{self._base}{self._params.login_path}",
            json=payload,
            timeout=self._params.timeout_seconds,
        )
        resp.raise_for_status()
        self._authenticated = True

    def get(self, path: str) -> dict:
        """Issue an authenticated GET and return the parsed JSON body."""
        self.authenticate()
        resp = self._session.get(f"{self._base}{path}", timeout=self._params.timeout_seconds)
        resp.raise_for_status()
        return resp.json()

    def post(self, path: str, json: Any | None = None) -> dict:
        """Issue an authenticated POST and return the parsed JSON body."""
        self.authenticate()
        resp = self._session.post(
            f"{self._base}{path}", json=json, timeout=self._params.timeout_seconds
        )
        resp.raise_for_status()
        return resp.json()

    def close(self) -> None:
        """Close the underlying session."""
        self._session.close()
        self._authenticated = False
