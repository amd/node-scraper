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

from nodescraper.models.analyzerargs import AnalyzerArgs
from nodescraper.plugins.inband.rocm.rocmdata import RocmDataModel


class RocmAnalyzerArgs(AnalyzerArgs):
    exp_rocm: Union[str, list] = Field(default_factory=list)

    @field_validator("exp_rocm", mode="before")
    @classmethod
    def validate_exp_rocm(cls, exp_rocm: Union[str, list]) -> list:
        """support str or list input for exp_rocm

        Args:
            exp_rocm (Union[str, list]): exp_rocm input

        Returns:
            list: exp_rocm list
        """
        if isinstance(exp_rocm, str):
            exp_rocm = [exp_rocm]

        return exp_rocm

    @classmethod
    def build_from_model(cls, datamodel: RocmDataModel) -> "RocmAnalyzerArgs":
        """build analyzer args from data model

        Args:
            datamodel (RocmDataModel): data model for plugin

        Returns:
            RocmAnalyzerArgs: instance of analyzer args class
        """
        return cls(exp_rocm=datamodel.rocm_version)
