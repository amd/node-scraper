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

from nodescraper.models import CollectorArgs


class PcieCollectorArgs(CollectorArgs):
    """Collector args for PCIe data.

    On ESXi, GPU/VF BDFs are resolved from ``esxcli hardware pci list`` by matching
    the expected PF/VF PCI device IDs (esxcli has no device filter). Provide them
    here; when both are unset no ESXi GPU BDFs are resolved. The caller populates
    these (e.g. from the system SKU).
    """

    devid_ep: Optional[int] = Field(
        default=None,
        description="Expected GPU PF PCI device ID (int, e.g. 0x75a3) for ESXi BDF resolution.",
    )
    devid_ep_vf: Optional[int] = Field(
        default=None,
        description="Expected GPU VF PCI device ID (int) for ESXi VF BDF resolution.",
    )
    collect_all_devices: bool = Field(
        default=False,
        description=(
            "When True, collect config space for non-AMD PCI devices into "
            "other_pcie_cfg_space (NICs, NVMe, etc.). Required for the NIC checks. "
            "Not supported on ESXi."
        ),
    )
    upstream_steps_to_collect: Optional[int] = Field(
        default=None,
        description="Number of upstream bridge hops to collect per endpoint. None = full path.",
    )
