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

from contextlib import suppress
from typing import ClassVar, Optional

import paramiko

from nodescraper.connection.inband.inband import InBandConnection
from nodescraper.connection.inband.inbandremote import RemoteShell, SSHConnectionError
from nodescraper.enums import EventCategory, EventPriority, ExecutionStatus
from nodescraper.interfaces.connectionmanager import ConnectionManager
from nodescraper.models import TaskResult
from nodescraper.utils import get_exception_traceback

from .amc_params import AmcInBandConnectionParams
from .bmc_relay import exec_relay_failure_detail, open_relay_channel


class AmcRemoteShell(RemoteShell):
    """RemoteShell for the AMC, reached through the BMC.

    Uses WarningPolicy because the AMC sits on the BMC's internal USB-ethernet
    link and its host key is never in the local known_hosts. When this connection
    fails, the plugin falls back to AmcShellHopConnectionManager which bypasses
    host-key checking on the BMC side.
    """

    host_key_policy = paramiko.WarningPolicy


class AmcInBandConnectionManager(ConnectionManager[InBandConnection, AmcInBandConnectionParams]):
    """Double-hop in-band shell: SSH to the BMC, then SSH to the AMC through the BMC.

    ``connection`` is a plain ``InBandConnection`` running commands and SFTP on the AMC, so
    existing in-band plugins run against the AMC unchanged.

    The BMC reaches the AMC through SSH port forwarding or, when the BMC prohibits forwarding,
    through a relay command run on the BMC (see AmcInBandConnectionParams.channel_mode).
    """

    CONNECTION_ARGS_MODEL: ClassVar[type[AmcInBandConnectionParams]] = AmcInBandConnectionParams

    _bmc_shell: Optional[RemoteShell] = None
    _relay_channel: Optional[paramiko.Channel] = None

    def connect(self) -> TaskResult:
        """Open BMC SSH, open a BMC->AMC channel, and attach a shell on the AMC.

        Returns:
            TaskResult: Connection result.
        """
        params = self.connection_args
        if not isinstance(params, AmcInBandConnectionParams):
            self._log_event(
                category=EventCategory.RUNTIME,
                description="No AMC in-band connection parameters provided",
                priority=EventPriority.CRITICAL,
                console_log=True,
            )
            self.result.status = ExecutionStatus.EXECUTION_FAILURE
            return self.result

        bmc_shell: Optional[RemoteShell] = None
        channel: Optional[paramiko.Channel] = None
        try:
            self.logger.info("Initializing AMC in-band: SSH to BMC %s", params.bmc_ssh.hostname)
            bmc_shell = RemoteShell(params.bmc_ssh)
            bmc_shell.connect_ssh()

            transport = bmc_shell.client.get_transport()
            if transport is None:
                raise SSHConnectionError("BMC SSH transport unavailable after connect")
            channel, used_mode = open_relay_channel(
                transport,
                str(params.amc_host),
                params.amc_port,
                mode=params.channel_mode,
                exec_relay_cmd=params.exec_relay_cmd,
                timeout=params.channel_timeout,
                logger=self.logger,
            )
            self.logger.info(
                "BMC->AMC channel to %s:%s open (mode=%s)",
                params.amc_host,
                params.amc_port,
                used_mode.value,
            )

            amc_shell = AmcRemoteShell(params.to_amc_ssh_params(), sock=channel)
            try:
                amc_shell.connect_ssh()
            except SSHConnectionError as exc:
                detail = exec_relay_failure_detail(channel)
                if detail:
                    raise SSHConnectionError(f"{exc} ({detail})") from exc
                raise

            self._bmc_shell = bmc_shell
            self._relay_channel = channel
            self.connection = amc_shell
        except Exception as exc:
            self._close(channel, bmc_shell)
            is_ssh_error = isinstance(exc, SSHConnectionError)
            self._log_event(
                category=EventCategory.SSH,
                description=str(exc) if is_ssh_error else f"AMC in-band connect failed: {exc}",
                data=None if is_ssh_error else get_exception_traceback(exc),
                priority=EventPriority.CRITICAL,
                console_log=True,
            )
            self.result.status = ExecutionStatus.EXECUTION_FAILURE
            self.connection = None
        return self.result

    @staticmethod
    def _close(channel: Optional[paramiko.Channel], bmc_shell: Optional[RemoteShell]) -> None:
        """Close the BMC->AMC channel and the BMC shell, ignoring teardown errors.

        Args:
            channel: BMC->AMC channel, if open.
            bmc_shell: BMC shell, if open.
        """
        if channel is not None:
            with suppress(Exception):
                channel.close()
        if bmc_shell is not None:
            with suppress(Exception):
                bmc_shell.client.close()

    def disconnect(self) -> None:
        """Close the AMC shell, then the BMC->AMC channel and BMC shell."""
        client = getattr(self.connection, "client", None)
        if client is not None:
            with suppress(Exception):
                client.close()
        self._close(self._relay_channel, self._bmc_shell)
        self._relay_channel = None
        self._bmc_shell = None
        super().disconnect()
