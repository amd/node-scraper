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

from nodescraper.models import AnalyzerArgs
from nodescraper.plugins.inband.kernel_module.kernel_module_data import (
    KernelModuleDataModel,
)


class KernelModuleAnalyzerArgs(AnalyzerArgs):
    kernel_modules: dict[str, dict] = {}
    modules_filter: list[str] = ["amd"]
    regex_match: bool = True

    @classmethod
    def build_from_model(cls, datamodel: KernelModuleDataModel) -> "KernelModuleAnalyzerArgs":
        """build analyzer args from data model

        Args:
            datamodel (KernelModuleDataModel): data model for plugin

        Returns:
            KernelModuleAnalyzerArgs: instance of analyzer args class
        """
        return cls(
            kernel_modules=datamodel.kernel_modules,
            modules_filter=datamodel.modules_filter,
            regex_match=datamodel.regex_match,
        )
