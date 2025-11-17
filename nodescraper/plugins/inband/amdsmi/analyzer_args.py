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

from nodescraper.models import AnalyzerArgs


class AmdSmiAnalyzerArgs(AnalyzerArgs):

    check_static_data: bool = False
    expected_gpu_processes: Optional[int] = None
    expected_max_power: Optional[int] = None
    expected_driver_version: Optional[str] = None
    expected_memory_partition_mode: Optional[str] = None
    expected_compute_partition_mode: Optional[str] = None
    expected_pldm_version: Optional[str] = None
    l0_to_recovery_count_error_threshold: Optional[int] = 3
    l0_to_recovery_count_warning_threshold: Optional[int] = 1
    vendorid_ep: Optional[str] = None
    vendorid_ep_vf: Optional[str] = None
    devid_ep: Optional[str] = None
    devid_ep_vf: Optional[str] = None
    sku_name: Optional[str] = None
    analysis_range_start: Optional[datetime] = None
    analysis_range_end: Optional[datetime] = None
