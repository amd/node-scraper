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

from pydantic import BaseModel, ConfigDict, Field, SecretStr
from pydantic.networks import IPvAnyAddress

from nodescraper.connection.inband.sshparams import SSHConnectionParams

from .redfish_connection import DEFAULT_REDFISH_API_ROOT


class RedfishConnectionParams(BaseModel):
    """Connection parameters for a Redfish (BMC) API endpoint."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    host: Union[IPvAnyAddress, str]
    username: str
    password: Optional[SecretStr] = None
    port: Optional[int] = Field(default=None, ge=1, le=65535)
    use_https: bool = True
    verify_ssl: bool = Field(
        default=True,
        description="Verify HTTPS server certificate. Set False for BMCs with self-signed certs.",
    )
    timeout_seconds: float = Field(default=10.0, gt=0, le=300)
    use_session_auth: bool = True
    api_root: str = Field(
        default=DEFAULT_REDFISH_API_ROOT,
        description="Redfish API path (e.g. 'redfish/v1'). Override for a different API version.",
    )


def redfish_params_to_ssh(
    params: Union[RedfishConnectionParams, dict],
    *,
    ssh_port: Optional[int] = None,
    key_filename: Optional[str] = None,
) -> SSHConnectionParams:
    """Map Redfish BMC credentials to SSH connection params for shell access."""
    if isinstance(params, dict):
        data = dict(params)
        ssh_port = data.pop("ssh_port", ssh_port if ssh_port is not None else 22)
        key_filename = data.pop("key_filename", key_filename)
        params = RedfishConnectionParams.model_validate(data)
    else:
        if ssh_port is None:
            ssh_port = 22

    return SSHConnectionParams(
        hostname=str(params.host),
        username=params.username,
        password=params.password,
        port=ssh_port,
        key_filename=key_filename,
    )
