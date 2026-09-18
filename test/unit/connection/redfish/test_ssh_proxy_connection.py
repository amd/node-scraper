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
import shlex
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from nodescraper.connection.inband.inband import BaseFileArtifact, CommandArtifact
from nodescraper.connection.redfish.ssh_proxy_connection import (
    CurlResponse,
    SshProxyRedfishConnection,
    parse_curl_headers,
)
from nodescraper.connection.redfish.ssh_proxy_manager import (
    RedfishSshProxyConnectionManager,
)
from nodescraper.connection.redfish.ssh_proxy_params import (
    RedfishSshProxyConnectionParams,
)
from nodescraper.enums import ExecutionStatus


class FakeRemoteShell:
    def __init__(self, status=200, headers="", body=b"{}"):
        self.status = status
        self.headers = headers
        self.body = body
        self.files = {}
        self.commands = []
        self._n = 0
        self.client = MagicMock()

    def run_command(self, command, sudo=False, timeout=30, strip=True):
        self.commands.append(command)
        if command == "mktemp":
            self._n += 1
            path = f"/tmp/ns-proxy-{self._n}"
            self.files[path] = b""
            return CommandArtifact(command=command, stdout=path, stderr="", exit_code=0)
        if command.startswith("curl"):
            parts = shlex.split(command)
            hdr = parts[parts.index("-D") + 1]
            body_path = parts[parts.index("-o") + 1]
            self.files[hdr] = self.headers.encode("utf-8")
            self.files[body_path] = self.body
            return CommandArtifact(command=command, stdout=str(self.status), stderr="", exit_code=0)
        if command.startswith("rm -f"):
            return CommandArtifact(command=command, stdout="", stderr="", exit_code=0)
        return CommandArtifact(command=command, stdout="", stderr="unexpected", exit_code=1)

    def read_file(self, filename, encoding="utf-8", strip=True):
        return BaseFileArtifact.from_bytes(
            filename=filename,
            raw_contents=self.files[filename],
            encoding=encoding,
            strip=strip,
        )


def test_parse_curl_headers_last_hop_wins():
    text = (
        "HTTP/1.1 301 Moved\n"
        "Location: /old\n"
        "\n"
        "HTTP/1.1 200 OK\n"
        "Location: /redfish/v1/TaskService/Tasks/1\n"
        "Content-Type: application/json\n"
        "\n"
    )
    headers = parse_curl_headers(text)
    assert headers["Location"] == "/redfish/v1/TaskService/Tasks/1"
    assert headers["Content-Type"] == "application/json"


def test_curl_response_json_and_ok():
    resp = CurlResponse(200, b'{"Id": "root"}')
    assert resp.ok
    assert resp.json() == {"Id": "root"}
    assert resp.reason == "OK"


def test_ssh_proxy_get_uses_quoted_internal_url():
    shell = FakeRemoteShell(
        headers="HTTP/1.1 200 OK\nContent-Type: application/json\n\n",
        body=b'{"RedfishVersion": "1.15.0"}',
    )
    conn = SshProxyRedfishConnection(shell, "http://192.0.2.10:80", api_root="redfish/v1")
    data = conn.get_service_root()
    assert data["RedfishVersion"] == "1.15.0"
    curl_cmds = [c for c in shell.commands if c.startswith("curl")]
    assert len(curl_cmds) == 1
    assert "http://192.0.2.10:80/redfish/v1" in curl_cmds[0]


def test_ssh_proxy_post_includes_json_body():
    shell = FakeRemoteShell(body=b'{"TaskState": "Running"}')
    conn = SshProxyRedfishConnection(shell, "http://192.0.2.10:80")
    resp = conn.post(
        "redfish/v1/Managers/dummy-amc/LogServices/Dump/Actions/LogService.CollectDiagnosticData",
        json={"DiagnosticDataType": "Manager"},
    )
    assert resp.status_code == 200
    curl_cmds = [c for c in shell.commands if c.startswith("curl")]
    assert "-X POST" in curl_cmds[0]
    assert "DiagnosticDataType" in curl_cmds[0]


def test_ssh_proxy_manager_connect_success(system_info):
    shell = FakeRemoteShell(body=b'{"RedfishVersion": "1.15.0"}')
    shell.connect_ssh = MagicMock()
    params = {
        "host": "192.0.2.10",
        "port": 80,
        "use_https": False,
        "ssh": {
            "hostname": "bmc.example.test",
            "username": "testuser",
            "key_filename": "/tmp/dummy_id",
        },
    }
    mgr = RedfishSshProxyConnectionManager(system_info=system_info, connection_args=params)
    with patch(
        "nodescraper.connection.redfish.ssh_proxy_manager.RemoteShell",
        return_value=shell,
    ):
        result = mgr.connect()
    assert result.status in (ExecutionStatus.UNSET, ExecutionStatus.OK)
    assert mgr.connection is not None


def test_ssh_proxy_params_require_ssh():
    with pytest.raises(ValidationError):
        RedfishSshProxyConnectionParams(host="192.0.2.10")
