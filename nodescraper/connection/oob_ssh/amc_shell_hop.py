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

import codecs
import re
import secrets
import shlex
import time
from contextlib import suppress
from typing import Any, Callable, ClassVar, Optional

from nodescraper.connection.inband.inband import (
    BaseFileArtifact,
    CommandArtifact,
    InBandConnection,
)
from nodescraper.connection.inband.inbandremote import RemoteShell, SSHConnectionError
from nodescraper.enums import EventCategory, EventPriority, ExecutionStatus
from nodescraper.interfaces.connectionmanager import ConnectionManager
from nodescraper.models import TaskResult
from nodescraper.utils import get_exception_traceback

from .amc_params import AmcInBandConnectionParams

# Console noise interleaved with command output on an AMC PTY: BSD syslog, kernel
# priority, or a kernel timestamp.
SHELL_NOISE_RE = re.compile(
    r"^(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s|<\d+>|\[\s*\d+\.\d+\])"
)
_PROMPT_ENDINGS = ("#", "$", ">")


def _drain(channel: Any, timeout: float) -> str:
    """Read until the channel is idle or the timeout expires.

    Args:
        channel (Any): SSH shell channel
        timeout (float): seconds to wait for the channel to go idle

    Returns:
        str: text read from the channel
    """
    buf = ""
    decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
    deadline = time.monotonic() + timeout
    idle_deadline = time.monotonic() + 0.05
    while time.monotonic() < deadline:
        if channel.recv_ready():
            chunk = channel.recv(65536)
            if not chunk:
                break
            buf += decoder.decode(chunk)
            idle_deadline = time.monotonic() + 0.05
        elif buf and time.monotonic() >= idle_deadline:
            break
        else:
            time.sleep(0.01)
    buf += decoder.decode(b"", final=True)
    return buf


def _read_until(channel: Any, predicate: Callable[[str], bool], timeout: float) -> str:
    """Read until predicate accepts the buffer or the timeout expires.

    Args:
        channel (Any): SSH shell channel
        predicate (Callable[[str], bool]): test applied to the text read so far
        timeout (float): seconds to wait

    Returns:
        str: text read from the channel

    Raises:
        SSHConnectionError: when the predicate is not met in time
    """
    buf = ""
    decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if channel.recv_ready():
            chunk = channel.recv(65536)
            if not chunk:
                raise SSHConnectionError("AMC SSH session closed")
            buf += decoder.decode(chunk)
            if predicate(buf):
                return buf
        else:
            time.sleep(0.01)
    buf += decoder.decode(b"", final=True)
    if predicate(buf):
        return buf
    raise SSHConnectionError("Timed out waiting for the AMC shell")


def _asks_host_key(buf: str) -> bool:
    """Return whether the buffer is an SSH host-key prompt.

    Args:
        buf (str): text read from the shell

    Returns:
        bool: True when the BMC ssh client is asking to trust the AMC key
    """
    low = buf.lower()
    return "yes/no" in low or "(yes/no" in low


def _needs_answer(buf: str) -> bool:
    """Return whether the login output is waiting for a reply.

    Args:
        buf (str): text read from the shell

    Returns:
        bool: True for a host-key prompt or a password prompt
    """
    return _asks_host_key(buf) or "password" in buf.lower()


def _at_prompt(buf: str) -> bool:
    """Return whether the last non-empty line looks like a shell prompt.

    Args:
        buf (str): text read from the shell

    Returns:
        bool: True when the last line ends with a prompt character
    """
    lines = [line.strip() for line in buf.splitlines() if line.strip()]
    if not lines:
        return False
    return lines[-1].endswith(_PROMPT_ENDINGS)


def _login_finished(buf: str) -> bool:
    """Return whether AMC login succeeded or was rejected.

    Args:
        buf (str): text read after the password was sent

    Returns:
        bool: True at a shell prompt or a permission-denied message
    """
    return "permission denied" in buf.lower() or _at_prompt(buf)


def _login(
    channel: Any, host: str, username: str, password: str, port: int, timeout: float
) -> None:
    """SSH from an open BMC shell to the AMC and wait for a prompt.

    Args:
        channel (Any): interactive shell channel on the BMC
        host (str): AMC address as seen from the BMC
        username (str): AMC SSH username
        password (str): AMC SSH password
        port (int): AMC SSH port
        timeout (float): seconds to wait for each prompt

    Returns:
        None

    Raises:
        SSHConnectionError: when login is rejected, the session closes, or a prompt never arrives
    """
    _drain(channel, timeout=min(0.2, timeout))
    target = f"{shlex.quote(username)}@{shlex.quote(host)}"
    channel.send(
        "exec ssh -p "
        f"{port} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null {target}\n"
    )
    buf = _read_until(channel, _needs_answer, timeout)
    if _asks_host_key(buf):
        channel.send("yes\n")
        buf = _read_until(channel, _needs_answer, timeout)
    if "password" in buf.lower():
        channel.send(f"{password}\n")
        buf = _read_until(channel, _login_finished, timeout)
    if "permission denied" in buf.lower():
        raise SSHConnectionError("AMC shell hop authentication failed")
    channel.send("dmesg -n 1 >/dev/null 2>&1; true\n")
    _drain(channel, timeout=min(0.5, timeout))


def _exit_code(line: str, end: str) -> Optional[int]:
    """Return the command exit code when line is the end sentinel.

    Args:
        line (str): one line of shell output
        end (str): end sentinel token

    Returns:
        Optional[int]: exit code, or None when line is not the sentinel
    """
    prefix = end + ":"
    stripped = line.strip()
    if not stripped.startswith(prefix):
        return None
    raw = stripped[len(prefix) :]
    if not raw.isdigit():
        return None
    return int(raw)


def _saw_exit(end: str) -> Callable[[str], bool]:
    """Build a predicate that is true once the end sentinel has been read.

    Args:
        end (str): end sentinel token

    Returns:
        Callable[[str], bool]: predicate over the text read so far
    """

    def predicate(buf: str) -> bool:
        return any(_exit_code(line, end) is not None for line in buf.split("\n")[:-1])

    return predicate


class ShellHopConnection(InBandConnection):
    """Run commands on the AMC through an interactive SSH session on the BMC."""

    def __init__(self, channel: Any) -> None:
        """Attach to a BMC shell that is already logged into the AMC.

        Args:
            channel (Any): interactive shell channel on the AMC
        """
        self.channel = channel

    def close(self) -> None:
        """Close the shell channel.

        Returns:
            None
        """
        with suppress(Exception):
            self.channel.close()

    def run_command(
        self,
        command: str,
        sudo: bool = False,
        timeout: int = 300,
        strip: bool = True,
    ) -> CommandArtifact:
        """Run a command on the AMC and return its output and exit code.

        Args:
            command (str): shell command string
            sudo (bool): prefix the command with sudo. Defaults to False.
            timeout (int): seconds to wait for the command sentinel. Defaults to 300.
            strip (bool): strip whitespace from stdout. Defaults to True.

        Returns:
            CommandArtifact: stdout, stderr, and the exit code carried by the sentinel
        """
        if sudo:
            command = f"sudo {command}"
        token = secrets.token_hex(8)
        start = f"__NS_S_{token}__"
        end = f"__NS_E_{token}__"
        wrapped = f"echo {start}; ( {command} ); status=$?; printf '\\n'; echo {end}:$status\n"
        try:
            self.channel.send(wrapped)
            raw = _read_until(self.channel, _saw_exit(end), float(timeout))
        except Exception as exc:  # noqa: BLE001
            return CommandArtifact(
                command=command,
                stdout="",
                stderr=str(exc),
                exit_code=124,
            )

        lines: list[str] = []
        exit_code = 0
        in_output = False
        for line in raw.splitlines():
            if line.strip() == start:
                in_output = True
                continue
            code = _exit_code(line, end)
            if code is not None:
                exit_code = code
                break
            if in_output and not SHELL_NOISE_RE.match(line):
                lines.append(line)
        stdout = "\n".join(lines)
        if strip:
            stdout = stdout.strip()
        return CommandArtifact(command=command, stdout=stdout, stderr="", exit_code=exit_code)

    def read_file(
        self, filename: str, encoding: str = "utf-8", strip: bool = True
    ) -> BaseFileArtifact:
        """Read a remote text file by running cat on the AMC.

        Args:
            filename (str): path on the AMC
            encoding (str): encoding used to decode the file. Defaults to utf-8.
            strip (bool): strip whitespace from the file text. Defaults to True.

        Returns:
            BaseFileArtifact: file contents

        Raises:
            OSError: when cat exits non-zero
        """
        result = self.run_command(f"cat {shlex.quote(filename)}", strip=False)
        if result.exit_code != 0:
            raise OSError(result.stderr or result.stdout or "cat failed")
        raw = result.stdout.encode(encoding, errors="replace")
        return BaseFileArtifact.from_bytes(
            filename=filename,
            raw_contents=raw,
            encoding=encoding,
            strip=strip,
        )


def open_amc_shell_hop(
    client: Any,
    host: str,
    username: str,
    password: str,
    timeout: float,
    port: int = 22,
) -> ShellHopConnection:
    """Open a BMC shell, SSH to the AMC, and return a connection over that shell.

    Args:
        client (Any): connected paramiko SSH client for the BMC
        host (str): AMC address as seen from the BMC
        username (str): AMC SSH username
        password (str): AMC SSH password
        timeout (float): seconds to wait for the AMC prompt
        port (int): AMC SSH port. Defaults to 22.

    Returns:
        ShellHopConnection: connection that runs commands on the AMC

    Raises:
        SSHConnectionError: when the AMC login fails
    """
    channel = client.invoke_shell(width=250, height=50)
    try:
        _login(channel, host, username, password, port, timeout)
    except Exception:
        with suppress(Exception):
            channel.close()
        raise
    return ShellHopConnection(channel)


class AmcShellHopConnectionManager(ConnectionManager[InBandConnection, AmcInBandConnectionParams]):
    """SSH to the BMC, then SSH from that BMC shell to the AMC.

    Any plugin can select this connection by name. The BMC ssh client prompts for the
    AMC password, so amc_password is required.
    """

    CONNECTION_ARGS_MODEL: ClassVar[type[AmcInBandConnectionParams]] = AmcInBandConnectionParams

    _bmc_shell: Optional[RemoteShell] = None

    def connect(self) -> TaskResult:
        """Open a BMC shell and log it into the AMC.

        Returns:
            TaskResult: Connection result.
        """
        params = self.connection_args
        if not isinstance(params, AmcInBandConnectionParams):
            return self._fail_connect(
                EventCategory.RUNTIME,
                "Cannot open an AMC shell hop: no connection details were provided.",
                "No AMC connection parameters provided for the shell hop",
            )
        if params.amc_password is None:
            return self._fail_connect(
                EventCategory.RUNTIME,
                "Cannot open an AMC shell hop: the AMC password is required.",
                "AMC shell hop requires amc_password because the BMC ssh client prompts for it",
            )

        bmc_shell: Optional[RemoteShell] = None
        try:
            self.logger.info("AMC shell hop: SSH to BMC %s", params.bmc_ssh.hostname)
            bmc_shell = RemoteShell(params.bmc_ssh)
            bmc_shell.connect_ssh()
            hop = open_amc_shell_hop(
                bmc_shell.client,
                str(params.amc_host),
                params.amc_username,
                params.amc_password.get_secret_value(),
                timeout=params.channel_timeout,
                port=params.amc_port,
            )
            self._bmc_shell = bmc_shell
            self.connection = hop
        except Exception as exc:
            if bmc_shell is not None:
                with suppress(Exception):
                    bmc_shell.client.close()
            is_ssh_error = isinstance(exc, SSHConnectionError)
            self._log_event(
                category=EventCategory.SSH,
                description=str(exc) if is_ssh_error else f"AMC shell hop failed: {exc}",
                data=None if is_ssh_error else get_exception_traceback(exc),
                priority=EventPriority.CRITICAL,
                console_log=True,
            )
            self.result.status = ExecutionStatus.EXECUTION_FAILURE
            self.connection = None
        return self.result

    def disconnect(self) -> None:
        """Close the AMC shell and the BMC SSH session.

        Returns:
            None
        """
        connection = self.connection
        if isinstance(connection, ShellHopConnection):
            connection.close()
        if self._bmc_shell is not None:
            with suppress(Exception):
                self._bmc_shell.client.close()
            self._bmc_shell = None
        super().disconnect()
