from typing import Optional

from pydantic import Field

from nodescraper.models import CollectorArgs


class DeviceEnumerationCollectorArgs(CollectorArgs):
    """Collector args for device enumeration.

    On ESXi, GPUs and their SR-IOV VFs are counted by PCI device ID (esxcli has no
    device filter). Provide the expected PF/VF device IDs here; when unset the ESXi
    GPU/VF counts are skipped. The caller populates these (e.g. from the system SKU).
    """

    devid_ep: Optional[int] = Field(
        default=None,
        description="Expected GPU PF PCI device ID (int, e.g. 0x75a3) for ESXi device counting.",
    )
    devid_ep_vf: Optional[int] = Field(
        default=None,
        description="Expected GPU VF PCI device ID (int) for ESXi VF counting.",
    )
