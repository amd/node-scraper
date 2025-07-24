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
from pydantic import Field, field_validator

from nodescraper.models import AnalyzerArgs
from nodescraper.plugins.inband.os.osdata import OsDataModel


class BiosAnalyzerArgs(AnalyzerArgs):
    exp_bios_version: list[str] = Field(default_factory=list)
    regex_match: bool = False

    @field_validator("exp_bios_version", mode="before")
    @classmethod
    def validate_exp_bios_version(cls, exp_bios_version: str | list) -> list:
        """support str or list input for exp_bios_version

        Args:
            exp_bios_version (str | list): expected BIOS version(s) to match against

        Returns:
            list: a list of expected BIOS versions
        """
        if isinstance(exp_bios_version, str):
            exp_bios_version = [exp_bios_version]

        return exp_bios_version

    @classmethod
    def build_from_model(cls, datamodel: OsDataModel) -> "BiosAnalyzerArgs":
        """build analyzer args from data model

        Args:
            datamodel (BiosDataModel): data model for plugin

        Returns:
            BiosAnalyzerArgs: instance of analyzer args class
        """
        return cls(exp_bios_version=datamodel.bios_version)
