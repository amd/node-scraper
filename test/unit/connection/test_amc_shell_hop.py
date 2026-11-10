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
import re
from unittest.mock import MagicMock, patch

import pytest
from pydantic import SecretStr

from nodescraper.connection.inband.inband import CommandArtifact
from nodescraper.connection.inband.inbandremote import SSHConnectionError
from nodescraper.connection.inband.sshparams import SSHConnectionParams
from nodescraper.connection.oob_ssh.amc_manager import AmcInBandConnectionManager
from nodescraper.connection.oob_ssh.amc_params import AmcInBandConnectionParams
from nodescraper.connection.oob_ssh.amc_shell_hop import (
    AmcShellHopConnectionManager,
    ShellHopConnection,
    open_amc_shell_hop,
)
from nodescraper.connection.oob_ssh.bmc_relay import ChannelMode
from nodescraper.enums import ExecutionStatus, SystemLocation
from nodescraper.models import SystemInfo
from nodescraper.plugins.ooband.bmc_journalctl.bmc_journalctl_plugin import (
    AmcJournalctlPlugin,
)


class ScriptedChannel:
    """PTY stand-in that answers the shell-hop login and command sentinels."""

    def __init__(
        self,
        password: str = "secret",
        exit_code: int = 0,
        output: str = "hello",
        reject: bool = False,
    ) -> None:
        self.password = password
        self.exit_code = exit_code
        self.output = output
        self.reject = reject
        self.sent: list[str] = []
        self.pending = b""
        self.closed = False

    def send(self, data: str) -> None:
        self.sent.append(data)
        if data.startswith("exec ssh ") and not self.pending:
            self.pending = b"Are you sure you want to continue connecting (yes/no)? "
        elif data.strip() == "yes":
            self.pending = b"password: "
        elif data.strip() == self.password:
            self.pending = b"Permission denied\n" if self.reject else b"amc:~# \n"
        elif "__NS_S_" in data:
            start_match = re.search(r"__NS_S_[0-9a-f]+__", data)
            end_match = re.search(r"__NS_E_[0-9a-f]+__", data)
            if start_match is None or end_match is None:
                return
            start = start_match.group(0)
            end = end_match.group(0)
            self.pending = (
                f"{data}\n{start}\nJan 01 00:00:00 amc kernel: noise\n"
                f"{self.output}\n{end}:{self.exit_code}\n"
            ).encode()

    def recv_ready(self) -> bool:
        return bool(self.pending)

    def recv(self, nbytes: int) -> bytes:
        chunk = self.pending[:nbytes]
        self.pending = self.pending[nbytes:]
        return chunk

    def close(self) -> None:
        self.closed = True


class _SplitChunkChannel:
    """Channel that delivers one command reply in two reads."""

    def __init__(
        self,
        output: str = "line",
        exit_code_text: str = "141",
        split_output: bool = False,
    ) -> None:
        self.output = output
        self.exit_code_text = exit_code_text
        self.split_output = split_output
        self.sent: list[str] = []
        self.chunks: list[bytes] = []

    def send(self, data: str) -> None:
        self.sent.append(data)
        start_match = re.search(r"__NS_S_[0-9a-f]+__", data)
        end_match = re.search(r"__NS_E_[0-9a-f]+__", data)
        if start_match is None or end_match is None:
            return
        start = start_match.group(0)
        end = end_match.group(0)
        payload = f"{start}\n{self.output}\n{end}:{self.exit_code_text}\n".encode()
        if self.split_output:
            cut = payload.index(self.output.encode()) + 1
        else:
            marker = f"{end}:1".encode()
            cut = payload.index(marker) + len(marker)
        self.chunks = [payload[:cut], payload[cut:]]

    def recv_ready(self) -> bool:
        return bool(self.chunks)

    def recv(self, nbytes: int) -> bytes:
        return self.chunks.pop(0)


def _system_info() -> SystemInfo:
    return SystemInfo(name="bmc-under-test", location=SystemLocation.LOCAL)


def _params(mode: ChannelMode = ChannelMode.AUTO) -> AmcInBandConnectionParams:
    return AmcInBandConnectionParams(
        bmc_ssh=SSHConnectionParams(
            hostname="10.1.1.8",
            username="root",
            password=SecretStr("bmc-secret"),
        ),
        amc_username="root",
        amc_password=SecretStr("secret"),
        channel_mode=mode,
    )


def test_shell_hop_runs_command_and_drops_console_noise():
    channel = ScriptedChannel(exit_code=3, output="journal line")
    client = MagicMock()
    client.invoke_shell.return_value = channel

    hop = open_amc_shell_hop(client, "192.168.31.1", "root", "secret", timeout=2)
    result = hop.run_command("journalctl --no-pager -q")

    assert result.exit_code == 3
    assert result.stdout == "journal line"
    assert "noise" not in result.stdout
    ssh_command = next(line for line in channel.sent if line.startswith("exec ssh "))
    assert "-p 22 " in ssh_command
    assert "StrictHostKeyChecking=no" in ssh_command
    assert any(line.strip() == "secret" for line in channel.sent)


def test_shell_hop_rejects_a_bad_password():
    channel = ScriptedChannel(reject=True)
    client = MagicMock()
    client.invoke_shell.return_value = channel

    with pytest.raises(SSHConnectionError):
        open_amc_shell_hop(client, "192.168.31.1", "root", "secret", timeout=2)
    assert channel.closed


def test_shell_hop_reads_a_file():
    channel = ScriptedChannel(output="payload")
    connection = ShellHopConnection(channel)
    artifact = connection.read_file("/var/log/demo.txt")

    assert artifact.contents_str() == "payload"
    assert "cat " in channel.sent[-1]


def test_shell_hop_read_file_can_keep_surrounding_whitespace():
    channel = ScriptedChannel(output="  padded  ")
    connection = ShellHopConnection(channel)
    artifact = connection.read_file("/var/log/demo.txt", strip=False)

    assert artifact.contents_str() == "  padded  "


def test_shell_hop_uses_the_configured_port():
    channel = ScriptedChannel()
    client = MagicMock()
    client.invoke_shell.return_value = channel

    open_amc_shell_hop(client, "192.168.31.1", "root", "secret", timeout=2, port=2222)

    ssh_command = next(line for line in channel.sent if line.startswith("exec ssh "))
    assert "-p 2222 " in ssh_command


def test_shell_hop_treats_a_closed_session_as_login_failure():
    channel = ScriptedChannel()
    channel.recv_ready = lambda: True
    channel.recv = lambda nbytes: b""
    client = MagicMock()
    client.invoke_shell.return_value = channel

    with pytest.raises(SSHConnectionError, match="AMC SSH session closed"):
        open_amc_shell_hop(client, "192.168.31.1", "root", "secret", timeout=2)
    assert channel.closed


def test_shell_hop_waits_for_a_complete_exit_sentinel():
    channel = _SplitChunkChannel(exit_code_text="141")
    result = ShellHopConnection(channel).run_command("true")

    assert result.exit_code == 141
    assert result.stdout == "line"


def test_shell_hop_joins_a_character_split_across_reads():
    channel = _SplitChunkChannel(output="\u2603", split_output=True)
    result = ShellHopConnection(channel).run_command("printf")

    assert result.stdout == "\u2603"


@patch("nodescraper.connection.oob_ssh.amc_shell_hop.RemoteShell")
@patch("nodescraper.connection.oob_ssh.amc_shell_hop.open_amc_shell_hop")
def test_shell_hop_connection_manager_logs_into_the_amc(mock_hop, mock_remote):
    bmc = MagicMock()
    mock_remote.return_value = bmc
    hop = ShellHopConnection(ScriptedChannel())
    mock_hop.return_value = hop

    manager = AmcShellHopConnectionManager(system_info=_system_info(), connection_args=_params())
    result = manager.connect()

    assert result.status == ExecutionStatus.OK
    assert manager.connection is hop
    mock_remote.return_value.connect_ssh.assert_called_once()
    mock_hop.assert_called_once()
    assert mock_hop.call_args.kwargs["port"] == 22


def test_shell_hop_connection_manager_requires_a_password():
    params = _params()
    params.amc_password = None
    params.amc_key_filename = "/tmp/dummy-key"
    manager = AmcShellHopConnectionManager(system_info=_system_info(), connection_args=params)
    result = manager.connect()

    assert result.status == ExecutionStatus.EXECUTION_FAILURE
    assert manager.connection is None


@patch("nodescraper.connection.oob_ssh.amc_manager.AmcRemoteShell")
@patch("nodescraper.connection.oob_ssh.amc_manager.open_relay_channel")
@patch("nodescraper.connection.oob_ssh.amc_manager.RemoteShell")
def test_direct_mode_does_not_shell_hop(mock_remote, mock_relay, mock_amc):
    bmc = MagicMock()
    bmc.client.get_transport.return_value = MagicMock()
    mock_remote.return_value = bmc
    mock_relay.return_value = (MagicMock(), ChannelMode.DIRECT_TCPIP)
    mock_amc.return_value.connect_ssh.side_effect = SSHConnectionError("tunnel closed")

    manager = AmcInBandConnectionManager(
        system_info=_system_info(),
        connection_args=_params(ChannelMode.DIRECT_TCPIP),
    )
    result = manager.connect()

    assert result.status == ExecutionStatus.EXECUTION_FAILURE
    assert manager.connection is None


def test_amc_journal_plugin_falls_back_to_the_shell_hop_connection(system_info):
    assert AmcJournalctlPlugin.FALLBACK_CONNECTION_TYPE is AmcShellHopConnectionManager

    primary = MagicMock()
    primary.connection = None
    primary.connection_args = _params()
    primary.result.status = ExecutionStatus.UNSET

    def fail_connect():
        primary.connection = None
        primary.result.status = ExecutionStatus.EXECUTION_FAILURE
        return primary.result

    primary.connect.side_effect = fail_connect
    created = {}

    class RecordingFallback:
        def __init__(self, **kwargs):
            self.connection_args = kwargs["connection_args"]
            self.connection = MagicMock()
            self.connection.run_command.return_value = CommandArtifact(
                command="journalctl", stdout="", stderr="", exit_code=0
            )
            self.result = MagicMock(status=ExecutionStatus.OK)
            self.closed = False
            created["manager"] = self

        def connect(self):
            return self.result

        def safe_disconnect(self):
            self.closed = True

    plugin = AmcJournalctlPlugin(system_info=system_info, connection_manager=primary)
    with patch.object(AmcJournalctlPlugin, "FALLBACK_CONNECTION_TYPE", RecordingFallback):
        result = plugin.collect()

    assert result.status == ExecutionStatus.OK
    assert created["manager"].closed is True
    assert created["manager"].connection.run_command.called
