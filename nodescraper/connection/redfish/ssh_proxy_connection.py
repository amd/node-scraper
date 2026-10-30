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

import json as json_lib
import logging
import secrets
import shlex
from http import HTTPStatus
from typing import Any, Optional, Union
from urllib.parse import urljoin, urlparse

from requests.structures import CaseInsensitiveDict

from nodescraper.connection.inband.inband import CommandArtifact
from nodescraper.connection.inband.inbandremote import RemoteShell, SSHConnectionError

from .redfish_connection import RedfishConnection, RedfishConnectionError
from .redfish_path import RedfishPath


def parse_curl_headers(header_text: str) -> CaseInsensitiveDict:
    """Parse curl -D header blocks into a case-insensitive map (last hop wins).

    Args:
        header_text: Raw HTTP header dump from curl -D.

    Returns:
        CaseInsensitiveDict of header name to value.
    """
    headers: CaseInsensitiveDict = CaseInsensitiveDict()
    for block in header_text.replace("\r\n", "\n").split("\n\n"):
        for line in block.split("\n"):
            if not line or line.lower().startswith("http/"):
                continue
            if ":" not in line:
                continue
            name, value = line.split(":", 1)
            headers[name.strip()] = value.strip()
    return headers


_DEAD_SESSION_MARKERS = (
    "server connection dropped",
    "ssh session not active",
    "session not active",
    "timeout opening channel",
    "socket is closed",
    "connection reset",
    "not connected",
    "ssh channel failed",
)


def _is_dead_session(detail: str) -> bool:
    """Return whether an SSH error means the BMC session is gone.

    Args:
        detail: Error text from the SSH client.

    Returns:
        True when the session should be opened again.
    """
    text = detail.lower()
    return any(marker in text for marker in _DEAD_SESSION_MARKERS)


def split_curl_stdout(raw: str, marker: str) -> tuple[int, str, bytes]:
    """Split curl stdout into an HTTP status, headers, and body.

    Args:
        raw: Combined curl stdout.
        marker: Trailer token written by curl -w.

    Returns:
        Status code, header text, and body bytes.
    """
    payload, found, tail = raw.rpartition(marker)
    if not found:
        raise RedfishConnectionError("curl stdout is missing the status trailer")
    if payload.endswith("\n"):
        payload = payload[:-1]
    try:
        status_code = int(tail.strip())
    except (TypeError, ValueError) as exc:
        raise RedfishConnectionError(f"curl status is not numeric: {tail.strip()}") from exc
    header_text, body_text = _split_header_and_body(payload)
    return status_code, header_text, body_text.encode("utf-8")


def _split_header_and_body(payload: str) -> tuple[str, str]:
    """Split a curl -D - payload into header text and body text.

    Args:
        payload: Headers and body with the status trailer removed.

    Returns:
        Header text and body text. Header text is empty when no header block is present.
    """
    for separator in ("\r\n\r\n", "\n\n"):
        index = payload.find(separator)
        if index != -1:
            return payload[:index], payload[index + len(separator) :]
    return "", payload


def _url_path(url: str) -> str:
    """Return the URL path for log messages (no host).

    Args:
        url: Absolute URL.

    Returns:
        Path component or the original string.
    """
    return urlparse(url).path or url


class CurlResponse:
    """Minimal requests.Response stand-in for curl over SSH."""

    def __init__(
        self,
        status_code: int,
        content: bytes,
        headers: Optional[CaseInsensitiveDict] = None,
    ):
        self.status_code = status_code
        self.content = content
        self.headers = headers or CaseInsensitiveDict()

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 400

    @property
    def reason(self) -> str:
        try:
            return HTTPStatus(self.status_code).phrase
        except ValueError:
            return ""

    @property
    def text(self) -> str:
        return self.content.decode("utf-8", errors="replace")

    def json(self) -> Any:
        """Parse the body as JSON.

        Returns:
            Parsed object, or empty dict when the body is empty.
        """
        if not self.content or not self.text.strip():
            return {}
        return json_lib.loads(self.text)


class SshProxyRedfishConnection(RedfishConnection):
    """Redfish client that runs curl on a remote BMC to reach an internal AMC URL."""

    def __init__(
        self,
        shell: RemoteShell,
        base_url: str,
        timeout: float = 60.0,
        api_root: Optional[str] = None,
    ):
        super().__init__(
            base_url=base_url,
            username="",
            password=None,
            timeout=timeout,
            use_session_auth=False,
            verify_ssl=False,
            api_root=api_root,
        )
        self._shell = shell

    def _cmd_timeout(self) -> int:
        return max(int(self.timeout) + 15, 30)

    def _curl(self, url: str, extra_flags: str = "") -> CurlResponse:
        """Run curl over SSH, and open the session again once if it has dropped.

        Args:
            url: Absolute URL to request.
            extra_flags: Extra curl arguments, including a trailing space when set.

        Returns:
            CurlResponse with status, headers, and body.
        """
        if self._shell._proxy_ssh_down:
            raise RedfishConnectionError("SSH session not active")
        try:
            return self._curl_once(url, extra_flags)
        except RedfishConnectionError as exc:
            if not _is_dead_session(str(exc)):
                raise
            logging.getLogger("nodescraper").info(
                "SSH proxy session dropped; reconnecting and retrying %s",
                _url_path(url),
            )
            try:
                self._shell.reconnect_ssh()
            except (SSHConnectionError, OSError) as reconnect_exc:
                self._shell._proxy_ssh_down = True
                raise RedfishConnectionError(
                    f"SSH proxy reconnect failed: {reconnect_exc}"
                ) from reconnect_exc
            try:
                return self._curl_once(url, extra_flags)
            except RedfishConnectionError as retry_exc:
                if _is_dead_session(str(retry_exc)):
                    self._shell._proxy_ssh_down = True
                raise

    def _curl_once(self, url: str, extra_flags: str = "") -> CurlResponse:
        """Run one curl on the BMC and read the response from that command.

        Args:
            url: Absolute URL to request.
            extra_flags: Extra curl arguments, including a trailing space when set.

        Returns:
            CurlResponse with status, headers, and body.
        """
        marker = f"NODESCRAPER{secrets.token_hex(16)}"
        max_time = max(int(self.timeout), 1)
        trailer = f"\n{marker}%{{http_code}}\n"
        cmd = (
            f"curl -sS --max-time {max_time} -D - -o - "
            f"-w {shlex.quote(trailer)} {extra_flags}{shlex.quote(url)}"
        )
        result: CommandArtifact = self._shell.run_command(
            cmd, timeout=self._cmd_timeout(), strip=False
        )
        if _is_dead_session(result.stderr or ""):
            raise RedfishConnectionError((result.stderr or "").strip() or "SSH session not active")
        raw = result.stdout or ""
        detail = (result.stderr or result.stdout or "").strip()
        if marker not in raw:
            raise RedfishConnectionError(f"curl to {_url_path(url)} failed: {detail}")
        try:
            status_code, header_text, body = split_curl_stdout(raw, marker)
        except RedfishConnectionError as exc:
            raise RedfishConnectionError(f"curl to {_url_path(url)} failed: {exc}") from exc
        if result.exit_code != 0 and status_code == 0:
            raise RedfishConnectionError(f"curl to {_url_path(url)} failed: {detail}")
        return CurlResponse(
            status_code=status_code,
            content=body,
            headers=parse_curl_headers(header_text),
        )

    def _ensure_session(self):
        return None

    def _login_session(self) -> None:
        return None

    def get_response(self, path: Union[str, "RedfishPath"]) -> CurlResponse:
        """GET a Redfish path via curl on the SSH host.

        Args:
            path: Redfish URI or RedfishPath.

        Returns:
            CurlResponse with status, headers, and body.
        """
        return self._curl(self._abs_url(str(path)))

    def post(
        self, path: Union[str, "RedfishPath"], json: Optional[dict[str, Any]] = None
    ) -> CurlResponse:
        """POST JSON to a Redfish path via curl on the SSH host.

        Args:
            path: Redfish URI or RedfishPath.
            json: JSON body.

        Returns:
            CurlResponse with status, headers, and body.
        """
        payload = json_lib.dumps(json or {})
        extra = (
            f"-X POST -H {shlex.quote('Content-Type: application/json')} "
            f"-d {shlex.quote(payload)} "
        )
        return self._curl(self._abs_url(str(path)), extra_flags=extra)

    def get(self, path: RedfishPath) -> dict[str, Any]:
        """GET a Redfish path and return the JSON body.

        Args:
            path: Redfish path object.

        Returns:
            Parsed JSON object.

        Raises:
            RedfishConnectionError: When the GET fails or the body is not JSON.
        """
        path_str = str(path)
        resp = self.get_response(path_str)
        if not resp.ok:
            raise RedfishConnectionError(
                f"GET {path_str} failed: {resp.status_code} {resp.reason}",
                response=resp,
            )
        try:
            data = resp.json()
        except (ValueError, json_lib.JSONDecodeError) as exc:
            raise RedfishConnectionError(
                f"GET {path_str} returned invalid JSON: {exc}",
                response=resp,
            ) from exc
        if not isinstance(data, dict):
            raise RedfishConnectionError(
                f"GET {path_str} did not return a JSON object",
                response=resp,
            )
        return data

    def copy(self) -> "SshProxyRedfishConnection":
        """Return a wrapper that shares the same SSH session.

        Returns:
            SshProxyRedfishConnection using the same RemoteShell.
        """
        return SshProxyRedfishConnection(
            shell=self._shell,
            base_url=self.base_url,
            timeout=self.timeout,
            api_root=self.api_root,
        )

    def close(self) -> None:
        self._session = None
        self._session_token = None
        self._session_uri = None

    def _abs_url(self, path: str) -> str:
        if path.startswith("http"):
            return path
        return urljoin(self.base_url + "/", path.lstrip("/"))
