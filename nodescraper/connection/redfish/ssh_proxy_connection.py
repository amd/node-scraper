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
import shlex
from http import HTTPStatus
from typing import Any, Optional, Union
from urllib.parse import urljoin, urlparse

from requests.structures import CaseInsensitiveDict

from nodescraper.connection.inband.inband import BinaryFileArtifact, CommandArtifact
from nodescraper.connection.inband.inbandremote import RemoteShell

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

    def _mktemp(self) -> str:
        artifact = self._shell.run_command("mktemp", timeout=self._cmd_timeout())
        path = (artifact.stdout or "").strip()
        if artifact.exit_code != 0 or not path:
            raise RedfishConnectionError("Failed to create remote temp file via mktemp")
        return path

    def _rm(self, *paths: str) -> None:
        quoted = " ".join(shlex.quote(p) for p in paths if p)
        if quoted:
            self._shell.run_command(f"rm -f {quoted}", timeout=self._cmd_timeout())

    def _curl(self, url: str, extra_flags: str = "") -> CurlResponse:
        header_path = self._mktemp()
        body_path = self._mktemp()
        try:
            max_time = max(int(self.timeout), 1)
            cmd = (
                f"curl -sS --max-time {max_time} -D {shlex.quote(header_path)} "
                f"-o {shlex.quote(body_path)} -w '%{{http_code}}' {extra_flags}"
                f"{shlex.quote(url)}"
            )
            result: CommandArtifact = self._shell.run_command(
                cmd, timeout=self._cmd_timeout(), strip=True
            )
            status_str = (result.stdout or "").strip()
            try:
                status_code = int(status_str)
            except (TypeError, ValueError) as exc:
                detail = result.stderr or result.stdout or str(exc)
                raise RedfishConnectionError(f"curl to {_url_path(url)} failed: {detail}") from exc
            if result.exit_code != 0 and status_code == 0:
                raise RedfishConnectionError(
                    f"curl to {_url_path(url)} failed: {result.stderr or result.stdout}"
                )
            header_art = self._shell.read_file(header_path, encoding="utf-8", strip=False)
            body_art = self._shell.read_file(body_path, encoding=None)
            if isinstance(header_art, BinaryFileArtifact):
                header_text = header_art.contents.decode("utf-8", errors="replace")
            else:
                header_text = header_art.contents_str()
            if isinstance(body_art, BinaryFileArtifact):
                body = body_art.contents
            else:
                body = body_art.contents_str().encode("utf-8")
            return CurlResponse(
                status_code=status_code,
                content=body,
                headers=parse_curl_headers(header_text),
            )
        finally:
            self._rm(header_path, body_path)

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
