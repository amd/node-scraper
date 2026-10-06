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

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.networks import IPvAnyAddress

from nodescraper.connection.inband.sshparams import SSHConnectionParams

from .redfish_connection import DEFAULT_REDFISH_API_ROOT


class RedfishSshProxyConnectionParams(BaseModel):
    """Redfish over SSH: curl on the BMC to an AMC address reachable from that host.

    Single-target mode supplies host and ssh. Multi-target mode supplies targets,
    and each entry has its own ssh block and AMC host.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    target_key: Optional[str] = Field(
        default=None,
        description="Identifier used when this entry appears inside a targets list.",
    )
    targets: Optional[list["RedfishSshProxyConnectionParams"]] = Field(
        default=None,
        description="BMC SSH-proxy targets. Each entry has its own ssh block and AMC host.",
    )
    max_workers: Optional[int] = Field(
        default=None,
        ge=1,
        description=(
            "Max concurrent collection threads. Defaults to the target count, capped at 32."
        ),
    )
    host: Optional[Union[IPvAnyAddress, str]] = Field(
        default=None,
        description="Redfish host as seen from the SSH target (internal AMC address).",
    )
    ssh: Optional[SSHConnectionParams] = Field(
        default=None,
        description="SSH parameters for the BMC that can reach host.",
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

    @model_validator(mode="after")
    def _validate_target_config(self) -> "RedfishSshProxyConnectionParams":
        """Require host and ssh unless a targets list is set.

        Returns:
            RedfishSshProxyConnectionParams: This params object.
        """
        if self.targets:
            return self
        if self.host is None or self.ssh is None:
            raise ValueError("Either targets or both host and ssh must be provided.")
        return self

    @property
    def is_multi_target(self) -> bool:
        """True when one or more targets are configured via the targets list.

        Returns:
            bool: True when targets is non-empty.
        """
        return bool(self.targets)


RedfishSshProxyConnectionParams.model_rebuild()
