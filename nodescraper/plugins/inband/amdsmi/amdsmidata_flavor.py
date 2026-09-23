"""amd-smi data model that widens the base (guest/bare-metal only) ``AmdSmiDataModel``
field types to also accept the mxGPU host-driver and guest-VF model variants. The
collector picks the concrete model per driver flavor; this model only relaxes the
annotations so those instances are accepted and serialized. The base ``AmdSmiDataModel``
and its consumers are unchanged.
"""

from __future__ import annotations

from typing import Optional, Union

from pydantic import Field

from nodescraper.plugins.inband.amdsmi.amdsmidata import (
    AmdSmiDataModel,
    AmdSmiListItem,
    AmdSmiMetric,
    AmdSmiStatic,
    AmdSmiVersion,
    BadPages,
    Topo,
    XgmiLinks,
    XgmiMetrics,
)

from .amdsmidata_guest import GuestAmdSmiMetric, GuestAmdSmiStatic
from .amdsmidata_host import (
    HostDriverAmdSmiListItem,
    HostDriverAmdSmiMetric,
    HostDriverAmdSmiStatic,
    HostDriverAmdSmiVersion,
    HostDriverBadPages,
    HostDriverTopo,
    HostDriverXgmiLinks,
    HostDriverXgmiMetrics,
)


class AmdSmiFlavorDataModel(AmdSmiDataModel):
    """AmdSmiDataModel with host/guest driver-flavor model variants allowed."""

    # Base (guest/bare-metal) type is listed first; the collector builds the right
    # concrete instance per flavor, so widening the annotation is sufficient.
    # Widening the base annotations is an intentional LSP override (invariant list),
    # so the type: ignore[assignment] markers below are expected.
    version: Optional[Union[AmdSmiVersion, HostDriverAmdSmiVersion]] = None  # type: ignore[assignment]
    gpu_list: Optional[list[Union[AmdSmiListItem, HostDriverAmdSmiListItem]]] = Field(  # type: ignore[assignment]
        default_factory=list
    )
    topology: Optional[list[Union[Topo, HostDriverTopo]]] = Field(default_factory=list)  # type: ignore[assignment]
    bad_pages: Optional[list[Union[BadPages, HostDriverBadPages]]] = Field(default_factory=list)  # type: ignore[assignment]
    static: Optional[list[Union[AmdSmiStatic, GuestAmdSmiStatic, HostDriverAmdSmiStatic]]] = Field(  # type: ignore[assignment]
        default_factory=list
    )
    metric: Optional[list[Union[AmdSmiMetric, GuestAmdSmiMetric, HostDriverAmdSmiMetric]]] = Field(  # type: ignore[assignment]
        default_factory=list
    )
    xgmi_metric: Optional[list[Union[XgmiMetrics, HostDriverXgmiMetrics]]] = Field(  # type: ignore[assignment]
        default_factory=list
    )
    xgmi_link: Optional[list[Union[XgmiLinks, HostDriverXgmiLinks]]] = Field(default_factory=list)  # type: ignore[assignment]
