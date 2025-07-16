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
import re
from typing import ClassVar

from nodescraper.models import AnalyzerArgs
from nodescraper.plugins.inband.kernel_module.kernel_module_data import (
    KernelModuleDataModel,
)


class KernelModuleAnalyzerArgs(AnalyzerArgs):
    kernel_modules: dict[str, dict] = {}

    DEFAULT_REGEX_FILTER: ClassVar[list[str]] = ["amd"]
    DEFAULT_REGEX_MATCH: ClassVar[bool] = True
    regex_filter: list[str] = DEFAULT_REGEX_FILTER
    regex_match: bool = DEFAULT_REGEX_MATCH

    @classmethod
    def build_from_model(cls, datamodel: KernelModuleDataModel) -> "KernelModuleAnalyzerArgs":
        """build analyzer args from data model and filter by regex_filter

        Args:
            datamodel (KernelModuleDataModel): data model for plugin

        Returns:
            KernelModuleAnalyzerArgs: instance of analyzer args class
        """

        pattern_regex = re.compile("|".join(cls.DEFAULT_REGEX_FILTER), re.IGNORECASE)
        filtered_mods = {
            name: data
            for name, data in datamodel.kernel_modules.items()
            if pattern_regex.search(name)
        }

        return cls(
            kernel_modules=filtered_mods,
            regex_filter=cls.DEFAULT_REGEX_FILTER,
            regex_match=cls.DEFAULT_REGEX_MATCH,
        )
