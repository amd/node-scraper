from .amdsmi_flavor_collector import AmdSmiFlavorCollector
from .amdsmi_plugin import AmdSmiPlugin
from .amdsmidata_flavor import AmdSmiFlavorDataModel


class AmdSmiFlavorPlugin(AmdSmiPlugin):
    """amd-smi plugin variant with driver-flavor collection.

    Detects the loaded driver flavor and issues flavor-appropriate amd-smi commands:
      - mxGPU host driver (gim on Linux, amdgpuv on ESXi) -> HostDriver* models
      - guest amdgpu on a virtual function inside a VM     -> Guest* models
      - bare-metal amdgpu on physical hardware             -> base AmdSmi* models
    Data is built into AmdSmiFlavorDataModel. The base AmdSmiPlugin (guest/bare-metal
    only) is left unchanged for callers that do not need host/VF support.
    """

    DATA_MODEL = AmdSmiFlavorDataModel  # type: ignore[assignment]
    COLLECTOR = AmdSmiFlavorCollector
