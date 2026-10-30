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
from typing import Union

from pydantic import Field, field_validator

from nodescraper.models import AnalyzerArgs
from nodescraper.plugins.inband.bios.biosdata import BiosDataModel


class BiosAnalyzerArgs(AnalyzerArgs):
    exp_bios_version: list[str] = Field(
        default_factory=list,
        description="Expected BIOS version(s) to match against collected value (str or list).",
    )
    exp_server_vendor: list[str] = Field(
        default_factory=list,
        description="Expected server vendor(s) from DMI system manufacturer (str or list).",
    )
    exp_server_model: list[str] = Field(
        default_factory=list,
        description="Expected server model(s) from DMI system product name (str or list).",
    )
    regex_match: bool = Field(
        default=False,
        description="If True, match expected BIOS, vendor, and model values as regex; otherwise exact match.",
    )

    @field_validator("exp_bios_version", "exp_server_vendor", "exp_server_model", mode="before")
    @classmethod
    def validate_expected_str_list(cls, value: Union[str, list, None]) -> list:
        """support str or list input for expected string fields

        Args:
            value (Union[str, list, None]): expected value(s) to match against

        Returns:
            list: a list of expected values
        """
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        return value

    @classmethod
    def build_from_model(cls, datamodel: BiosDataModel) -> "BiosAnalyzerArgs":
        """build analyzer args from data model

        Args:
            datamodel (BiosDataModel): data model for plugin

        Returns:
            BiosAnalyzerArgs: instance of analyzer args class
        """
        return cls(
            exp_bios_version=datamodel.bios_version,
            exp_server_vendor=(
                [datamodel.server_vendor] if datamodel.server_vendor is not None else []
            ),
            exp_server_model=[datamodel.server_model] if datamodel.server_model is not None else [],
        )
