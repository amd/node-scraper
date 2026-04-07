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
from datetime import datetime
from typing import Optional

from pydantic import Field

from nodescraper.models import AnalyzerArgs


class AmdSmiAnalyzerArgs(AnalyzerArgs):
    check_static_data: bool = Field(
        default=False,
        description="If True, run static data checks (e.g. driver version, partition mode).",
    )
    expected_gpu_processes: Optional[int] = Field(
        default=None, description="Expected number of GPU processes."
    )
    expected_max_power: Optional[int] = Field(
        default=None, description="Expected maximum power value (e.g. watts)."
    )
    expected_driver_version: Optional[str] = Field(
        default=None, description="Expected AMD driver version string."
    )
    expected_memory_partition_mode: Optional[str] = Field(
        default=None, description="Expected memory partition mode (e.g. sp3, dp)."
    )
    expected_compute_partition_mode: Optional[str] = Field(
        default=None, description="Expected compute partition mode."
    )
    expected_pldm_version: Optional[str] = Field(
        default=None, description="Expected PLDM version string."
    )
    l0_to_recovery_count_error_threshold: Optional[int] = Field(
        default=3,
        description="L0-to-recovery count above which an error is raised.",
    )
    l0_to_recovery_count_warning_threshold: Optional[int] = Field(
        default=1,
        description="L0-to-recovery count above which a warning is raised.",
    )
    vendorid_ep: Optional[str] = Field(
        default=None, description="Expected endpoint vendor ID (e.g. for PCIe)."
    )
    vendorid_ep_vf: Optional[str] = Field(
        default=None, description="Expected endpoint VF vendor ID."
    )
    devid_ep: Optional[str] = Field(default=None, description="Expected endpoint device ID.")
    devid_ep_vf: Optional[str] = Field(default=None, description="Expected endpoint VF device ID.")
    sku_name: Optional[str] = Field(default=None, description="Expected SKU name string for GPU.")
    expected_xgmi_speed: Optional[list[float]] = Field(
        default=None, description="Expected xGMI speed value(s) (e.g. link rate)."
    )
    analysis_range_start: Optional[datetime] = Field(
        default=None, description="Start of time range for time-windowed analysis."
    )
    analysis_range_end: Optional[datetime] = Field(
        default=None, description="End of time range for time-windowed analysis."
    )
