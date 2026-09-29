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
