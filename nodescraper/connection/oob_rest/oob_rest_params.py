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


class OobRestConnectionParams(BaseModel):
    """Connection parameters for a generic out-of-band REST controller.

    Covers controllers that authenticate with a username/password POST to a
    login endpoint and then serve JSON over HTTPS. The login endpoint and any
    extra payload fields are parameterized so a controller that expects extra
    login fields (e.g. ``{"tenant": "default"}``) can be configured without a
    controller-specific subclass.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    host: Union[IPvAnyAddress, str]
    username: str
    password: Optional[SecretStr] = None
    port: Optional[int] = Field(default=None, ge=1, le=65535)
    use_https: bool = True
    verify_ssl: bool = Field(
        default=False,
        description="Verify the HTTPS server certificate. Defaults to False because OOB "
        "controllers commonly serve self-signed certificates.",
    )
    timeout_seconds: float = Field(default=30.0, gt=0, le=300)
    login_path: str = Field(
        default="/v1/login",
        description="Path of the login endpoint the controller authenticates against.",
    )
    login_payload_extra: dict = Field(
        default_factory=dict,
        description="Extra fields merged into the login JSON payload alongside username and "
        'password (e.g. {"tenant": "default"} for a controller that requires it).',
    )
