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
from typing import Dict, Optional

from pydantic import Field

from nodescraper.models import AnalyzerArgs
from nodescraper.plugins.inband.package.packagedata import PackageDataModel


class PackageAnalyzerArgs(AnalyzerArgs):
    exp_package_ver: Dict[str, Optional[str]] = Field(
        default_factory=dict,
        description="Map package name -> expected version (None = any version). Checked against installed packages.",
    )
    regex_match: bool = Field(
        default=False,
        description="If True, match package versions with regex; otherwise exact or prefix match.",
    )
    rocm_regex: Optional[str] = Field(
        default=None,
        description="Optional regex to identify ROCm package version (used when enable_rocm_regex is True).",
    )
    enable_rocm_regex: bool = Field(
        default=False,
        description="If True, use rocm_regex (or default pattern) to extract ROCm version for checks.",
    )

    @classmethod
    def build_from_model(cls, datamodel: PackageDataModel) -> "PackageAnalyzerArgs":
        # Use custom rocm_regex from collection_args if enable_rocm_regex is true
        rocm_regex = None
        if datamodel.enable_rocm_regex and datamodel.rocm_regex:
            rocm_regex = datamodel.rocm_regex

        return cls(exp_package_ver=datamodel.version_info, rocm_regex=rocm_regex)
