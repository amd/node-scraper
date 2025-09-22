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

from nodescraper.models import AnalyzerArgs


class AmdSmiAnalyzerArgs(AnalyzerArgs):

    check_static_data: bool = True
    expected_gpu_processes: Optional[int] = 12
    expected_max_power: Optional[int] = 2
    expected_driver_version: Optional[str] = "5"
    expected_memory_partition_mode: Optional[str] = "test"
    expected_compute_partition_mode: Optional[str] = "test2"
    expected_pldm_version: Optional[str] = "test3"
    l0_to_recovery_count_error_threshold: Optional[int] = 1
    l0_to_recovery_count_warning_threshold: Optional[int] = 2
    vendorid_ep: Optional["str"] = "vendorid_ep"
    vendorid_ep_vf: Optional["str"] = "vendorid_ep_vf"
    devid_ep: Optional["str"] = "devid_ep"
    sku_name: Optional["str"] = "sku_name"
