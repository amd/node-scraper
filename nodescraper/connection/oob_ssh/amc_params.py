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

from typing import Optional, Union

from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator
from pydantic.networks import IPvAnyAddress

from nodescraper.connection.inband.sshparams import SSHConnectionParams

from .bmc_relay import DEFAULT_EXEC_RELAY_CMD, ChannelMode

# Internal address of the AMC as seen from the BMC (USB-ethernet link).
DEFAULT_AMC_HOST = "192.168.31.1"
DEFAULT_AMC_PORT = 22


class AmcInBandConnectionParams(BaseModel):
    """Parameters for a double-hop in-band shell: local -> BMC (SSH) -> AMC (SSH).

    The first hop (``bmc_ssh``) is a normal SSH connection to the BMC. The BMC then provides a
    byte stream to ``amc_host``:``amc_port`` (see ``channel_mode``), and a second SSH session runs
    over that stream, giving a real shell + SFTP on the AMC.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    bmc_ssh: SSHConnectionParams = Field(
        description="SSH parameters for the first hop: the BMC that can reach the AMC.",
    )
    amc_host: Union[IPvAnyAddress, str] = Field(
        default=DEFAULT_AMC_HOST,
        description="AMC address as reachable from the BMC (default: internal USB-ethernet IP).",
    )
    amc_port: int = Field(
        default=DEFAULT_AMC_PORT,
        ge=1,
        le=65535,
        description="SSH port on the AMC (default: 22).",
    )
    amc_username: str = Field(
        description="SSH username for the second hop (the AMC).",
    )
    amc_password: Optional[SecretStr] = Field(
        default=None,
        description="SSH password for the AMC. Use amc_key_filename for key auth instead.",
    )
    amc_key_filename: Optional[str] = Field(
        default=None,
        description="Path to a private key file for AMC authentication (optional).",
    )
    channel_timeout: float = Field(
        default=15.0,
        gt=0,
        le=300,
        description="Timeout (seconds) for opening the BMC->AMC channel.",
    )
    channel_mode: ChannelMode = Field(
        default=ChannelMode.AUTO,
        description=(
            "How the BMC reaches the AMC. 'direct-tcpip' uses SSH port forwarding on the BMC; "
            "'exec' runs exec_relay_cmd on the BMC and relays over its stdin/stdout; 'auto' tries "
            "direct-tcpip and switches to exec when the BMC prohibits port forwarding."
        ),
    )
    exec_relay_cmd: str = Field(
        default=DEFAULT_EXEC_RELAY_CMD,
        description=(
            "Relay command run on the BMC in exec mode. Must contain {host} and {port}, which are "
            "replaced with the shell-quoted AMC host and port. Example alternative: 'nc {host} {port}'."
        ),
    )

    @model_validator(mode="after")
    def _validate_auth(self) -> "AmcInBandConnectionParams":
        """Require at least one AMC auth method.

        Returns:
            AmcInBandConnectionParams: This params object.
        """
        if not self.amc_password and not self.amc_key_filename:
            raise ValueError(
                "Either amc_password or amc_key_filename must be provided for the AMC."
            )
        return self

    @model_validator(mode="after")
    def _validate_relay_cmd(self) -> "AmcInBandConnectionParams":
        """Require {host} and {port} placeholders in the relay command.

        Returns:
            AmcInBandConnectionParams: This params object.
        """
        if "{host}" not in self.exec_relay_cmd or "{port}" not in self.exec_relay_cmd:
            raise ValueError("exec_relay_cmd must contain both {host} and {port} placeholders.")
        return self

    def to_amc_ssh_params(self) -> SSHConnectionParams:
        """Build the SSHConnectionParams used for the second (AMC) hop.

        Returns:
            SSHConnectionParams: Params targeting the AMC (host/port/creds).
        """
        return SSHConnectionParams(
            hostname=str(self.amc_host),
            username=self.amc_username,
            password=self.amc_password,
            key_filename=self.amc_key_filename,
            port=self.amc_port,
        )
