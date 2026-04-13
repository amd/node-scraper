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
from typing import Optional

from pydantic import Field

from nodescraper.models.analyzerargs import AnalyzerArgs


class StorageAnalyzerArgs(AnalyzerArgs):
    min_required_free_space_abs: Optional[str] = Field(
        default=None,
        description="Minimum required free space per mount (e.g. '10G', '1T').",
    )
    min_required_free_space_prct: Optional[int] = Field(
        default=None,
        description="Minimum required free space as percentage of total (0–100).",
    )
    ignore_devices: Optional[list[str]] = Field(
        default_factory=list,
        description="Mount points or devices to exclude from free-space checks.",
    )
    check_devices: Optional[list[str]] = Field(
        default_factory=list,
        description="If non-empty, only these mount points or devices are checked.",
    )
    regex_match: bool = Field(
        default=False,
        description="If True, match device/mount names with regex; otherwise exact match.",
    )
