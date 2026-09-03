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
from typing import Dict, Literal, Optional, Union

from pydantic import Field

from nodescraper.models import AnalyzerArgs

from .pcie_data import BdfStr, PcieDataModel, PcieDeviceSnapshot
from .pcie_inventory import PROFILE_FULL_BOM, filter_inventory_fields

PcieInventoryProfile = Literal["full_bom", "pcie_link", "custom"]


class PcieAnalyzerArgs(AnalyzerArgs):
    """Arguments for PCIe analyzer

    Attributes:
        profile: Inventory field allowlist preset for expected value checks.
        expected_total_count: Expected PCI device count from inventory collection.
        expected_devices: Sparse per-BDF expected inventory field values.
        expected_pcie_snapshot: Sparse per-BDF expected register snapshot values.
        fail_on_extra_devices: Fail when inventory contains BDFs not listed in expected_devices.
        exp_speed: Expected PCIe speed (generation 1-5)
        exp_width: Expected PCIe width (1-16 lanes)
        exp_sriov_count: Expected SR-IOV VF count
        exp_gpu_count_override: Override expected GPU count
        exp_max_payload_size: Expected max payload size (int for all devices, dict for specific device IDs)
        exp_max_rd_req_size: Expected max read request size (int for all devices, dict for specific device IDs)
        exp_ten_bit_tag_req_en: Expected 10-bit tag request enable (int for all devices, dict for specific device IDs)
    """

    profile: PcieInventoryProfile = Field(
        default="full_bom",
        description="Inventory field allowlist: full_bom, pcie_link, or custom.",
    )
    expected_total_count: Optional[int] = Field(
        default=None,
        description="Expected PCI device count from inventory collection.",
    )
    expected_devices: Dict[BdfStr, Dict[str, str]] = Field(
        default_factory=dict,
        description="Sparse per-BDF expected inventory values; only set keys are validated.",
    )
    expected_pcie_snapshot: Optional[Dict[BdfStr, PcieDeviceSnapshot]] = Field(
        default=None,
        description="Sparse per-BDF expected register snapshot; only set fields are validated.",
    )
    fail_on_extra_devices: bool = Field(
        default=True,
        description="Fail when inventory contains BDFs not listed in expected_devices.",
    )
    exp_speed: int = Field(default=5, description="Expected PCIe link speed (generation 1–5).")
    exp_width: int = Field(default=16, description="Expected PCIe link width in lanes (1–16).")
    exp_sriov_count: Optional[int] = Field(
        default=None, description="Expected SR-IOV virtual function count."
    )
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

    @classmethod
    def build_from_model(cls, datamodel: PcieDataModel) -> "PcieAnalyzerArgs":
        """Build analyzer args from a collected PCIe data model for reference config generation."""
        expected_devices: Dict[BdfStr, Dict[str, str]] = {}
        expected_total_count: Optional[int] = None
        if datamodel.inventory is not None:
            expected_total_count = datamodel.inventory.total_count
            for bdf, device in datamodel.inventory.devices.items():
                fields = filter_inventory_fields(device, PROFILE_FULL_BOM)
                if fields:
                    expected_devices[bdf] = fields

        expected_pcie_snapshot = datamodel.pcie_snapshot or None
        return cls(
            expected_total_count=expected_total_count,
            expected_devices=expected_devices,
            expected_pcie_snapshot=expected_pcie_snapshot,
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
