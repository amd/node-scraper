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

from nodescraper.interfaces import AnalyzerArgs
from nodescraper.plugins.inband.os.osdata import OsDataModel


class OsAnalyzerArgs(AnalyzerArgs):
    exp_os: str | list = Field(default_factory=list)
    exact_match: bool = True

    @field_validator("exp_os", mode="before")
    @classmethod
    def validate_exp_os(cls, exp_os: str | list) -> list:
        """support str or list input for exp_os

        Args:
            exp_os (str | list): exp_os input

        Returns:
            list: exp_os list
        """
        if isinstance(exp_os, str):
            exp_os = [exp_os]

        return exp_os

    @classmethod
    def build_from_model(cls, datamodel: OsDataModel) -> "OsAnalyzerArgs":
        """build analyzer args from data model

        Args:
            datamodel (OsDataModel): data model for plugin

        Returns:
            OsAnalyzerArgs: instance of analyzer args class
        """
        return cls(exp_os=datamodel.os_version)
