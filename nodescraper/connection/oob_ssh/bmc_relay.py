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
"""Open a byte stream from an intermediate SSH host to a target only it can reach.

Used for jump-host style access (e.g. test host -> BMC -> AMC). The returned paramiko
channel behaves like a socket and can be passed as ``sock=`` to ``SSHClient.connect``.
"""
from __future__ import annotations

import logging
import shlex
from enum import Enum
from typing import Optional

import paramiko
from paramiko.common import OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED
from paramiko.ssh_exception import ChannelException

DEFAULT_EXEC_RELAY_CMD = "socat - TCP:{host}:{port}"
EXEC_RELAY_CHANNEL_NAME = "exec-relay"


class ChannelMode(str, Enum):
    """How the intermediate host reaches the target."""

    DIRECT_TCPIP = "direct-tcpip"
    EXEC = "exec"
    AUTO = "auto"


def open_relay_channel(
    transport: paramiko.Transport,
    host: str,
    port: int,
    mode: ChannelMode = ChannelMode.AUTO,
    exec_relay_cmd: str = DEFAULT_EXEC_RELAY_CMD,
    timeout: Optional[float] = None,
    logger: Optional[logging.Logger] = None,
) -> tuple[paramiko.Channel, ChannelMode]:
    """Open a channel on ``transport`` that carries a TCP stream to ``host``:``port``.

    Args:
        transport: Transport of the SSH session on the intermediate host.
        host: Target host as seen from the intermediate host.
        port: Target TCP port.
        mode: DIRECT_TCPIP uses SSH port forwarding; EXEC runs ``exec_relay_cmd`` on the
            intermediate host and relays over its stdin/stdout; AUTO tries DIRECT_TCPIP and
            switches to EXEC only when the server prohibits port forwarding.
        exec_relay_cmd: Relay command template with ``{host}`` and ``{port}`` placeholders.
        timeout: Seconds to wait for the channel to open.
        logger: Optional logger for the AUTO fallback notice.

    Returns:
        tuple[paramiko.Channel, ChannelMode]: The open channel and the mode actually used
        (DIRECT_TCPIP or EXEC).

    Raises:
        ChannelException: When port forwarding fails in DIRECT_TCPIP mode, or fails in AUTO mode
            for a reason other than being administratively prohibited.
    """
    mode = ChannelMode(mode)
    if mode in (ChannelMode.DIRECT_TCPIP, ChannelMode.AUTO):
        try:
            channel = transport.open_channel(
                "direct-tcpip", (host, port), ("127.0.0.1", 0), timeout=timeout
            )
            return channel, ChannelMode.DIRECT_TCPIP
        except ChannelException as exc:
            if (
                mode is ChannelMode.DIRECT_TCPIP
                or exc.code != OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED
            ):
                raise
            if logger is not None:
                logger.warning(
                    "SSH server prohibits port forwarding to %s:%s; relaying through '%s' instead",
                    host,
                    port,
                    exec_relay_cmd,
                )

    channel = transport.open_session(timeout=timeout)
    channel.set_name(EXEC_RELAY_CHANNEL_NAME)
    channel.exec_command(exec_relay_cmd.format(host=shlex.quote(host), port=int(port)))
    return channel, ChannelMode.EXEC


def exec_relay_failure_detail(channel: Optional[paramiko.Channel], wait: float = 1.0) -> str:
    """Describe why an exec relay ended, e.g. relay command missing or target refused.

    Args:
        channel: Channel returned by :func:`open_relay_channel`.
        wait: Seconds to wait for the relay's exit status.

    Returns:
        str: ``"relay exited with status N: <stderr>"`` when an exec relay exited non-zero,
        otherwise an empty string.
    """
    if channel is None or channel.get_name() != EXEC_RELAY_CHANNEL_NAME:
        return ""
    if not channel.status_event.wait(timeout=wait):
        return ""
    status = channel.recv_exit_status()
    if status <= 0:
        return ""
    stderr = b""
    while channel.recv_stderr_ready():
        chunk = channel.recv_stderr(4096)
        if not chunk:
            break
        stderr += chunk
    detail = stderr.decode(errors="replace").strip() or "(no stderr)"
    return f"relay exited with status {status}: {detail}"
