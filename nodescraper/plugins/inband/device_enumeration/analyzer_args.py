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
from typing import Any, Optional

from pydantic import field_validator

from nodescraper.models import AnalyzerArgs

from .deviceenumdata import DeviceEnumerationDataModel


class DeviceEnumerationAnalyzerArgs(AnalyzerArgs):
    cpu_count: Optional[list[int]] = None
    gpu_count: Optional[list[int]] = None
    vf_count: Optional[list[int]] = None

    @field_validator("cpu_count", "gpu_count", "vf_count", mode="before")
    @classmethod
    def normalize_to_list(cls, v: Any) -> Optional[list[int]]:
        """Convert single integer values to lists for consistent handling.

        Args:
            v: The input value (can be int, list[int], or None).

        Returns:
            Optional[list[int]]: The normalized list value or None.
        """
        if v is None:
            return None
        if isinstance(v, int):
            return [v]
        return v

    @classmethod
    def build_from_model(
        cls, datamodel: DeviceEnumerationDataModel
    ) -> "DeviceEnumerationAnalyzerArgs":
        """build analyzer args from data model

        Args:
            datamodel (DeviceEnumerationDataModel): data model for plugin

        Returns:
            DeviceEnumerationAnalyzerArgs: instance of analyzer args class
        """
        return cls(
            cpu_count=[datamodel.cpu_count] if datamodel.cpu_count is not None else None,
            gpu_count=[datamodel.gpu_count] if datamodel.gpu_count is not None else None,
            vf_count=[datamodel.vf_count] if datamodel.vf_count is not None else None,
        )
