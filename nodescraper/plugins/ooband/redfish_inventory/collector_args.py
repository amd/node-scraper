###############################################################################
#
# MIT License
#
# Copyright (c) 2026 Advanced Micro Devices, Inc.
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
from typing import Literal

from pydantic import Field, field_validator

from nodescraper.models import CollectorArgs

BMC_COLLECTIONS = ("Chassis", "Managers", "TelemetryService", "UpdateService", "Systems")
BMC_LINKS = (
    "Assembly",
    "PowerSubsystem",
    "Power",
    "FruDevices",
    "MetricReports",
    "MetricReportDefinitions",
    "FirmwareInventory",
)
SMC_COLLECTIONS = ("Systems", "UpdateService")
SMC_LINKS = ("Memory", "Processors", "FirmwareInventory")
INVENTORY_SWITCHES = (
    "chassis",
    "managers",
    "assembly",
    "power",
    "fru",
    "metrics",
    "update_service",
    "systems",
    "memory",
    "processors",
)
_ROOT_SWITCH = {
    "Chassis": "chassis",
    "Managers": "managers",
    "TelemetryService": "metrics",
    "UpdateService": "update_service",
    "Systems": "systems",
}
_LINK_SWITCH = {
    "Assembly": "assembly",
    "PowerSubsystem": "power",
    "Power": "power",
    "FruDevices": "fru",
    "MetricReports": "metrics",
    "MetricReportDefinitions": "metrics",
    "FirmwareInventory": "update_service",
    "Memory": "memory",
    "Processors": "processors",
}
_SWITCH_ROOTS: dict[str, tuple[str, ...]] = {
    "chassis": ("Chassis",),
    "managers": ("Managers",),
    "metrics": ("TelemetryService",),
    "update_service": ("UpdateService",),
    "systems": ("Systems",),
}
_SWITCH_LINKS = {
    "assembly": ("Assembly",),
    "power": ("PowerSubsystem", "Power"),
    "fru": ("FruDevices",),
    "metrics": ("MetricReports", "MetricReportDefinitions"),
    "update_service": ("FirmwareInventory",),
    "memory": ("Memory",),
    "processors": ("Processors",),
}


def _ordered_unique(names: tuple[str, ...]) -> list[str]:
    """Return names with duplicates removed and the first occurrence kept.

    Args:
        names: Collection or link names.

    Returns:
        Names in first-seen order.
    """
    return list(dict.fromkeys(names))


def _apply_enabled(
    names: list[str],
    name_switches: dict[str, str],
    forced: dict[str, tuple[str, ...]],
    enabled: dict[str, bool],
) -> list[str]:
    """Drop disabled inventory areas and add areas explicitly turned on.

    Args:
        names: Profile or caller-selected Redfish property names.
        name_switches: Property name to inventory switch.
        forced: Property names added when a switch is true.
        enabled: Switch overrides. A missing switch is left unchanged.

    Returns:
        Property names to follow.
    """
    kept: list[str] = []
    for name in names:
        switch = name_switches.get(name)
        if switch is not None and enabled.get(switch) is False:
            continue
        kept.append(name)
    for switch, extra in forced.items():
        if enabled.get(switch) is True:
            kept.extend(extra)
    return _ordered_unique(tuple(kept))


class RedfishInventoryCollectorArgs(CollectorArgs):
    """Select standard Redfish inventory collections to read from the service root."""

    profile: Literal["bmc", "smc", "all"] = Field(
        default="all",
        description="bmc reads chassis, managers, telemetry, firmware inventory, and systems. "
        "smc reads systems, memory, processors, and firmware inventory. all reads both.",
    )
    collections: list[str] = Field(
        default_factory=list,
        description="Extra service-root property names appended to the profile set. "
        "Duplicates are ignored. Empty leaves the profile unchanged.",
    )
    member_links: list[str] = Field(
        default_factory=list,
        description="Extra property names appended to the profile link set. "
        "Duplicates are ignored. Empty leaves the profile unchanged.",
    )
    max_pages: int = Field(
        default=1,
        ge=1,
        le=10_000,
        description="Maximum pages to keep for each collection, including the first page.",
    )
    enabled: dict[str, bool] = Field(
        default_factory=dict,
        description="Turn inventory areas on or off. Omitted areas stay at the profile default, "
        "and the default profile enables every area. update_service also follows "
        "FirmwareInventory members. Keys: chassis, managers, assembly, power, "
        "fru, metrics, update_service, systems, memory, processors.",
    )

    @field_validator("enabled")
    @classmethod
    def reject_unknown_switches(cls, value: dict[str, bool]) -> dict[str, bool]:
        """Reject inventory switch names that this collector does not know.

        Args:
            value: Requested enable flags.

        Returns:
            The same flags when every key is known.
        """
        unknown = sorted(set(value) - set(INVENTORY_SWITCHES))
        if unknown:
            raise ValueError(f"unknown inventory switches: {', '.join(unknown)}")
        return value

    def _profile_collections(self) -> list[str]:
        """Return the service-root collections selected by the profile.

        Args:
            None

        Returns:
            Service-root property names.
        """
        if self.profile == "bmc":
            return list(BMC_COLLECTIONS)
        if self.profile == "smc":
            return list(SMC_COLLECTIONS)
        return _ordered_unique(BMC_COLLECTIONS + SMC_COLLECTIONS)

    def _profile_links(self) -> list[str]:
        """Return the resource links selected by the profile.

        Args:
            None

        Returns:
            Property names followed from collected resources.
        """
        if self.profile == "bmc":
            return list(BMC_LINKS)
        if self.profile == "smc":
            return list(SMC_LINKS)
        return _ordered_unique(BMC_LINKS + SMC_LINKS)

    def selected_collections(self) -> list[str]:
        """Return the service-root collections this run will follow.

        Args:
            None

        Returns:
            Profile names with collections appended. Duplicates are dropped.
        """
        names = _ordered_unique(tuple(self._profile_collections() + list(self.collections)))
        return _apply_enabled(names, _ROOT_SWITCH, _SWITCH_ROOTS, self.enabled)

    def selected_links(self) -> list[str]:
        """Return the resource links this run will follow.

        Args:
            None

        Returns:
            Profile names with member_links appended. Duplicates are dropped.
        """
        names = _ordered_unique(tuple(self._profile_links() + list(self.member_links)))
        return _apply_enabled(names, _LINK_SWITCH, _SWITCH_LINKS, self.enabled)
