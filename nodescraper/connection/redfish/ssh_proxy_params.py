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

from pydantic import BaseModel, ConfigDict, Field
from pydantic.networks import IPvAnyAddress

from nodescraper.connection.inband.sshparams import SSHConnectionParams

from .redfish_connection import DEFAULT_REDFISH_API_ROOT


class RedfishSshProxyConnectionParams(BaseModel):
    """Redfish over SSH: curl on the BMC to an AMC (or other) address reachable from that host."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    host: Union[IPvAnyAddress, str] = Field(
        description="Redfish host as seen from the SSH target (internal AMC address).",
    )
    ssh: SSHConnectionParams = Field(
        description="SSH parameters for the BMC (or other host) that can reach host.",
    )
    port: Optional[int] = Field(default=80, ge=1, le=65535)
    use_https: bool = Field(
        default=False,
        description="Use https when curling Redfish from the SSH target.",
    )
    timeout_seconds: float = Field(default=60.0, gt=0, le=3600)
    api_root: str = Field(
        default=DEFAULT_REDFISH_API_ROOT,
        description="Redfish API path (e.g. redfish/v1).",
    )
