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

from typing import Any, Optional
from urllib.parse import urljoin

import requests
import urllib3  # type: ignore[import-untyped]
from pydantic import BaseModel
from requests import Response
from requests.auth import HTTPBasicAuth

DEFAULT_REDFISH_API_ROOT = "redfish/v1"


class RedfishGetResult(BaseModel):
    """Artifact for the result of a Redfish GET request."""

    path: str
    success: bool
    data: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    status_code: Optional[int] = None


class RedfishConnectionError(Exception):
    """Raised when a Redfish API request fails."""

    def __init__(self, message: str, response: Optional[Response] = None):
        super().__init__(message)
        self.response = response


class RedfishConnection:
    """Redfish REST client for GET requests."""

    def __init__(
        self,
        base_url: str,
        username: str,
        password: Optional[str] = None,
        timeout: float = 10.0,
        use_session_auth: bool = True,
        verify_ssl: bool = True,
        api_root: Optional[str] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_root = (api_root or DEFAULT_REDFISH_API_ROOT).strip("/")
        self.username = username
        self.password = password or ""
        self.timeout = timeout
        self.use_session_auth = use_session_auth
        self.verify_ssl = verify_ssl
        self._session: Optional[requests.Session] = None
        self._session_token: Optional[str] = None
        self._session_uri: Optional[str] = None  # For logout DELETE

    def _ensure_session(self) -> requests.Session:
        if self._session is None:
            if not self.verify_ssl:
                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            self._session = requests.Session()
            self._session.verify = self.verify_ssl
            self._session.headers["Content-Type"] = "application/json"
            self._session.headers["Accept"] = "application/json"
            if self.use_session_auth and self.password:
                self._login_session()
            elif self.password:
                self._session.auth = HTTPBasicAuth(self.username, self.password)
        return self._session

    def _login_session(self) -> None:
        """Create a Redfish session and set X-Auth-Token."""
        assert self._session is not None
        sess_url = urljoin(self.base_url + "/", f"{self.api_root}/SessionService/Sessions")
        payload = {"UserName": self.username, "Password": self.password}
        resp = self._session.post(
            sess_url,
            json=payload,
            timeout=self.timeout,
        )
        if not resp.ok:
            raise RedfishConnectionError(
                f"Session login failed: {resp.status_code} {resp.reason}", response=resp
            )
        self._session_token = resp.headers.get("X-Auth-Token")
        location = resp.headers.get("Location")
        if location:
            self._session_uri = (
                location
                if location.startswith("http")
                else urljoin(self.base_url + "/", location.lstrip("/"))
            )
        if self._session_token:
            self._session.headers["X-Auth-Token"] = self._session_token
        else:
            self._session.auth = HTTPBasicAuth(self.username, self.password)

    def get(self, path: str) -> dict[str, Any]:
        """GET a Redfish path and return the JSON body."""
        session = self._ensure_session()
        url = path if path.startswith("http") else urljoin(self.base_url + "/", path.lstrip("/"))
        resp = session.get(url, timeout=self.timeout)
        if not resp.ok:
            raise RedfishConnectionError(
                f"GET {path} failed: {resp.status_code} {resp.reason}",
                response=resp,
            )
        return resp.json()

    def run_get(self, path: str) -> RedfishGetResult:
        """Run a Redfish GET request and return a result object (no exception on failure)."""
        path_norm = path.strip()
        if not path_norm.startswith("/"):
            path_norm = "/" + path_norm
        try:
            data = self.get(path_norm)
            return RedfishGetResult(
                path=path_norm,
                success=True,
                data=data,
                status_code=200,
            )
        except RedfishConnectionError as e:
            status = e.response.status_code if e.response is not None else None
            return RedfishGetResult(
                path=path_norm,
                success=False,
                error=str(e),
                status_code=status,
            )
        except Exception as e:
            return RedfishGetResult(
                path=path_norm,
                success=False,
                error=str(e),
                status_code=None,
            )

    def get_service_root(self) -> dict[str, Any]:
        """GET service root (e.g. /redfish/v1/)."""
        return self.get(f"/{self.api_root}/")

    def close(self) -> None:
        """Release session and logout if session auth was used."""
        if self._session and self._session_uri:
            try:
                self._session.delete(self._session_uri, timeout=self.timeout)
            except Exception:
                pass
        self._session = None
        self._session_token = None
        self._session_uri = None

    def __enter__(self) -> RedfishConnection:
        self._ensure_session()
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
