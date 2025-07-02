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
from nodescraper.plugins.inband.kernel.kerneldata import KernelDataModel


class KernelAnalyzerArgs(AnalyzerArgs):
    exp_kernel: str | list = Field(default_factory=list)
    regex_match: bool = False

    @field_validator("exp_kernel", mode="before")
    @classmethod
    def validate_exp_kernel(cls, exp_kernel: str | list) -> list:
        """support str or list input for exp_kernel

        Args:
            exp_kernel (str | list): exp kernel input

        Returns:
            list: exp kernel list
        """
        if isinstance(exp_kernel, str):
            exp_kernel = [exp_kernel]

        return exp_kernel

    @classmethod
    def build_from_model(cls, datamodel: KernelDataModel) -> "KernelAnalyzerArgs":
        """build analyzer args from data model

        Args:
            datamodel (KernelDataModel): data model for plugin

        Returns:
            KernelAnalyzerArgs: instance of analyzer args class
        """
        return cls(exp_kernel=datamodel.kernel_version)
