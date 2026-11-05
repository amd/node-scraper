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
import subprocess
from unittest.mock import MagicMock, patch

from paramiko.ssh_exception import SSHException

from nodescraper.connection.inband.inbandlocal import LocalShell
from nodescraper.connection.inband.inbandremote import RemoteShell
from nodescraper.connection.inband.sshparams import SSHConnectionParams


@patch("nodescraper.connection.inband.inbandlocal.subprocess.run")
def test_localshell_string_uses_shell_true(mock_run):
    mock_run.return_value = MagicMock(stdout="ok\n", stderr="", returncode=0)

    shell = LocalShell()
    shell.run_command("ip addr show")

    assert mock_run.call_args.kwargs["shell"] is True


@patch("nodescraper.connection.inband.inbandlocal.subprocess.run")
def test_localshell_string_with_sudo(mock_run):
    mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)

    shell = LocalShell()
    shell.run_command("cat /etc/shadow", sudo=True)

    assert mock_run.call_args.args[0] == "sudo -n cat /etc/shadow"
    assert mock_run.call_args.kwargs["stdin"] is subprocess.DEVNULL


@patch("nodescraper.connection.inband.inbandlocal.subprocess.run")
def test_localshell_timeout_returns_exit_124(mock_run):
    mock_run.side_effect = subprocess.TimeoutExpired(
        cmd="sleep 5", timeout=1, output=b"", stderr=b""
    )

    artifact = LocalShell().run_command("sleep 5", timeout=1)

    assert artifact.exit_code == 124
    assert "timed out" in artifact.stderr


@patch("nodescraper.connection.inband.inbandremote.paramiko.SSHClient")
def test_remoteshell_sudo_password_is_newline_terminated(mock_client_cls):
    """sudo -S reads a line, so the password written to stdin must end with a newline."""
    stdin, stdout, stderr = MagicMock(), MagicMock(), MagicMock()
    stdout.read.return_value = b""
    stderr.read.return_value = b""
    stdout.channel.recv_exit_status.return_value = 0
    mock_client_cls.return_value.exec_command.return_value = (stdin, stdout, stderr)

    shell = RemoteShell(
        SSHConnectionParams(hostname="127.0.0.1", username="user", password="hunter2")
    )
    shell.run_command("cat /etc/shadow", sudo=True)

    stdin.write.assert_called_once_with("hunter2\n")
    stdout.channel.close.assert_called_once()


@patch("nodescraper.connection.inband.inbandremote.paramiko.SSHClient")
def test_remoteshell_ssh_exception_is_a_failed_command(mock_client_cls):
    mock_client_cls.return_value.exec_command.side_effect = SSHException("Timeout opening channel.")
    shell = RemoteShell(
        SSHConnectionParams(hostname="127.0.0.1", username="user", password="secret")
    )
    artifact = shell.run_command("mktemp")
    assert artifact.exit_code == 124
    assert artifact.stderr == "Timeout opening channel."


def _sftp_file(data: bytes) -> MagicMock:
    handle = MagicMock()
    handle.read.return_value = data
    handle.__enter__.return_value = handle
    handle.__exit__.return_value = False
    return handle


@patch("nodescraper.connection.inband.inbandremote.paramiko.SSHClient")
def test_reconnect_ssh_opens_a_new_client(mock_client_cls):
    clients = []

    def factory():
        client = MagicMock()
        client.get_transport.return_value.channel_timeout = None
        clients.append(client)
        return client

    mock_client_cls.side_effect = factory
    shell = RemoteShell(
        SSHConnectionParams(hostname="127.0.0.1", username="user", password="secret")
    )
    shell.reconnect_ssh()
    assert len(clients) == 2
    clients[0].close.assert_called_once()
    clients[1].connect.assert_called_once()
    assert shell.client is clients[1]
    assert clients[1].get_transport.return_value.channel_timeout == 60


@patch("nodescraper.connection.inband.inbandremote.paramiko.SSHClient")
def test_read_files_uses_one_sftp_session(mock_client_cls):
    sftp = MagicMock()
    sftp.open.side_effect = [
        _sftp_file(b"HTTP/1.1 200 OK\n\n"),
        _sftp_file(b"{}"),
    ]
    mock_client_cls.return_value.open_sftp.return_value = sftp
    shell = RemoteShell(
        SSHConnectionParams(hostname="127.0.0.1", username="user", password="secret")
    )
    contents = shell.read_files(["/tmp/headers", "/tmp/body"])
    assert contents == [b"HTTP/1.1 200 OK\n\n", b"{}"]
    mock_client_cls.return_value.open_sftp.assert_called_once()
    sftp.close.assert_called_once()
