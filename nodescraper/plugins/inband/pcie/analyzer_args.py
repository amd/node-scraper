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
from typing import Dict, Optional, Union

from nodescraper.models import AnalyzerArgs


class PcieAnalyzerArgs(AnalyzerArgs):
    """Arguments for PCIe analyzer

    Attributes:
        exp_speed: Expected PCIe speed (generation 1-5)
        exp_width: Expected PCIe width (1-16 lanes)
        exp_sriov_count: Expected SR-IOV VF count
        exp_gpu_count_override: Override expected GPU count
        exp_max_payload_size: Expected max payload size (int for all devices, dict for specific device IDs)
        exp_max_rd_req_size: Expected max read request size (int for all devices, dict for specific device IDs)
        exp_ten_bit_tag_req_en: Expected 10-bit tag request enable (int for all devices, dict for specific device IDs)
    """

    exp_speed: int = 5
    exp_width: int = 16
    exp_sriov_count: int = 0
    exp_gpu_count_override: Optional[int] = None
    exp_max_payload_size: Optional[Union[Dict[int, int], int]] = None
    exp_max_rd_req_size: Optional[Union[Dict[int, int], int]] = None
    exp_ten_bit_tag_req_en: Optional[Union[Dict[int, int], int]] = None


def normalize_to_dict(
    value: Optional[Union[Dict[int, int], int]], vendorid_ep: int
) -> Dict[int, int]:
    """Normalize int or dict values to dict format using vendorid_ep as key for int values"""
    if value is None:
        return {}
    if isinstance(value, int):
        return {vendorid_ep: value}
    if isinstance(value, dict):
        return value
    return {}
