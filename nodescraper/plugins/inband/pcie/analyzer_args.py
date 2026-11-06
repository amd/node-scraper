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

from pydantic import Field

from nodescraper.models import AnalyzerArgs


class PcieAnalyzerArgs(AnalyzerArgs):
    """Arguments for PCIe analyzer

    Attributes:
        exp_speed: Expected PCIe speed (generation 1-6)
        exp_width: Expected PCIe width (1-16 lanes)
        exp_sriov_count: Expected SR-IOV VF count
        exp_gpu_count_override: Override expected GPU count
        exp_max_payload_size: Expected max payload size (int for all devices, dict for specific device IDs)
        exp_max_rd_req_size: Expected max read request size (int for all devices, dict for specific device IDs)
        exp_ten_bit_tag_req_en: Expected 10-bit tag request enable (int for all devices, dict for specific device IDs)
        analyze_other_devices: Also run error checks on the other PCI Express devices
        exp_nic_count: Expected number of physical network controllers (NICs) enumerated via lspci
        exp_nic_speed: Expected NIC PCIe link speed (generation 1-6)
        exp_nic_width: Expected NIC PCIe link width in lanes (1-16)
    """

    exp_speed: int = Field(default=5, description="Expected PCIe link speed (generation 1–6).")
    exp_width: int = Field(default=16, description="Expected PCIe link width in lanes (1–16).")
    exp_sriov_count: int = Field(default=0, description="Expected SR-IOV virtual function count.")
    exp_gpu_count_override: Optional[int] = Field(
        default=None, description="Override expected GPU count for validation."
    )
    exp_max_payload_size: Optional[Union[Dict[int, int], int]] = Field(
        default=None,
        description="Expected max payload size: int for all devices, or dict keyed by device ID.",
    )
    exp_max_rd_req_size: Optional[Union[Dict[int, int], int]] = Field(
        default=None,
        description="Expected max read request size: int for all devices, or dict keyed by device ID.",
    )
    exp_ten_bit_tag_req_en: Optional[Union[Dict[int, int], int]] = Field(
        default=None,
        description="Expected 10-bit tag request enable: int for all devices, or dict keyed by device ID.",
    )
    analyze_other_devices: bool = Field(
        default=False,
        description=(
            "When True, also check the PCI Express devices in "
            "other_pcie_cfg_space for AER, status, lane and device errors."
        ),
    )
    exp_nic_count: Optional[int] = Field(
        default=None,
        description=(
            "Expected number of physical network controllers (NICs) bucketed "
            "from the collected PCI devices. Ports of a multi-port NIC count "
            "once and SR-IOV VFs are excluded. Only checked when set. Requires the "
            "collector to run with collect_all_devices=True."
        ),
    )
    exp_nic_speed: Optional[int] = Field(
        default=None,
        description="Expected NIC PCIe link speed (generation 1-6). Only checked when set.",
    )
    exp_nic_width: Optional[int] = Field(
        default=None,
        description="Expected NIC PCIe link width in lanes (1-16). Only checked when set.",
    )


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
