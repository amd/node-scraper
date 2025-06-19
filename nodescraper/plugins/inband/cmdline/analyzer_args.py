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
from pydantic import BaseModel, Field, field_validator


class CmdlineAnalyzerArgs(BaseModel):
    required_cmdline: str | list = Field(default_factory=list)
    banned_cmdline: str | list = Field(default_factory=list)

    model_config = {"extra": "forbid"}

    @field_validator("required_cmdline", mode="before")
    @classmethod
    def validate_required_cmdline(cls, required_cmdline: str | list) -> list:
        """support str or list input for required_cmdline

        Args:
            required_cmdline (str | list): required command line arguments

        Returns:
            list: list of required command line arguments
        """
        if isinstance(required_cmdline, str):
            required_cmdline = [required_cmdline]

        return required_cmdline

    @field_validator("banned_cmdline", mode="before")
    @classmethod
    def validate_banned_cmdline(cls, banned_cmdline: str | list) -> list:
        """support str or list input for banned_cmdline

        Args:
            banned_cmdline (str | list): banned command line arguments

        Returns:
            list: a list of banned command line arguments
        """
        if isinstance(banned_cmdline, str):
            banned_cmdline = [banned_cmdline]

        return banned_cmdline
