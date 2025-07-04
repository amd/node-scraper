###############################################################################
#
# MIT License
#
# Copyright (c) 2025 Advanced Micro Devices, Inc.
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
from typing import Any

from pydantic import BaseModel, Field, field_validator


class DkmsAnalyzerArgs(BaseModel):
    dkms_status: str | list = Field(default_factory=list)
    dkms_version: str | list = Field(default_factory=list)
    regex_match: bool = False

    model_config = {"extra": "forbid"}

    def model_post_init(self, __context: Any) -> None:
        if not self.dkms_status and not self.dkms_version:
            raise ValueError("At least one of dkms_status or dkms_version must be provided")

    @field_validator("dkms_status", mode="before")
    @classmethod
    def validate_dkms_status(cls, dkms_status: str | list) -> list:
        """support str or list input for dkms_status

        Args:
            dkms_status (str | list): dkms status to check

        Returns:
            list: list of dkms status
        """
        if isinstance(dkms_status, str):
            dkms_status = [dkms_status]

        return dkms_status

    @field_validator("dkms_version", mode="before")
    @classmethod
    def validate_dkms_version(cls, dkms_version: str | list) -> list:
        """support str or list input for dkms_version

        Args:
            dkms_version (str | list): dkms version to check

        Returns:
            list: list of dkms version
        """
        if isinstance(dkms_version, str):
            dkms_version = [dkms_version]

        return dkms_version
