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
import re
from typing import Dict, FrozenSet, Iterable, Optional

from .pcie_data import BdfStr, PcieInventory, PcieInventoryDevice

PROFILE_FULL_BOM: FrozenSet[str] = frozenset(
    {
        "type",
        "description",
        "vendor",
        "device",
        "subvendor",
        "subdevice",
        "revision",
        "driver",
        "driver_version",
        "slot",
        "speed",
        "width",
        "link_training",
    }
)

PROFILE_PCIE_LINK: FrozenSet[str] = frozenset(
    {
        "description",
        "vendor",
        "device",
        "subvendor",
        "subdevice",
        "speed",
        "width",
        "link_training",
        "lnkctl",
        "lnksta",
        "lnkctl2",
        "lnksta2",
    }
)

PROFILE_FIELD_ALLOWLISTS: Dict[str, FrozenSet[str]] = {
    "full_bom": PROFILE_FULL_BOM,
    "pcie_link": PROFILE_PCIE_LINK,
}

BDF_HEADER_RE = re.compile(
    r"^(?P<bdf>[0-9a-f]{4}:[0-9a-f]{2}:[0-9a-f]{2}\.[0-9a-f])\s+"
    r"(?P<type>[^:]+):\s+(?P<desc>.+)$",
    re.IGNORECASE,
)
VENDOR_DEVICE_RE = re.compile(r"\[(?P<vendor>[0-9a-fA-F]{4}):(?P<device>[0-9a-fA-F]{4})\]")
REVISION_RE = re.compile(r"\(rev (?P<revision>[0-9a-fA-F]+)\)", re.IGNORECASE)
SUBSYSTEM_RE = re.compile(
    r"^\s*Subsystem: .+\[(?P<subvendor>[0-9a-fA-F]{4}):(?P<subdevice>[0-9a-fA-F]{4})\]",
    re.IGNORECASE,
)
CONTROL_RE = re.compile(r"^\s*Control:\s+(?P<control>.+)$", re.IGNORECASE)
STATUS_RE = re.compile(r"^\s*Status:\s+(?P<status>.+)$", re.IGNORECASE)
IRQ_RE = re.compile(r"^\s*Interrupt: .+IRQ (?P<irq>\d+)", re.IGNORECASE)
DRIVER_RE = re.compile(r"^\s*Kernel driver in use:\s+(?P<driver>\S+)", re.IGNORECASE)
LNKSTA_RE = re.compile(
    r"^\s*LnkSta:\s+Speed (?P<speed>[^,(]+)(?:\s*\((?P<speed_lt>[^)]+)\))?,"
    r"\s+Width (?P<width>[^,(]+)(?:\s*\((?P<width_lt>[^)]+)\))?",
    re.IGNORECASE,
)
LNKCTL_RE = re.compile(r"^\s*LnkCtl:\s+(?P<lnkctl>.+)$", re.IGNORECASE)
LNKSTA2_RE = re.compile(r"^\s*LnkSta2:\s+(?P<lnksta2>.+)$", re.IGNORECASE)
LNKCTL2_RE = re.compile(r"^\s*LnkCtl2:\s+(?P<lnkctl2>.+)$", re.IGNORECASE)
SLOT_RE = re.compile(r"^\s*Physical Slot:\s+(?P<slot>.+)$", re.IGNORECASE)


def get_profile_fields(profile: str) -> Optional[FrozenSet[str]]:
    """Return the field allowlist for a profile name, or None for custom.
    Args:
        profile: full_bom, pcie_link, or custom.
    Returns:
        Frozen set of inventory field names, or None when profile is custom.
    """
    return PROFILE_FIELD_ALLOWLISTS.get(profile)


def split_lspci_device_blocks(lspci_text: str) -> Dict[str, str]:
    """Split lspci verbose output into per-BDF text blocks.
    Args:
        lspci_text: Raw lspci -D -xx -vv output.
    Returns:
        Mapping of BDF to that device's text block.
    """
    blocks: Dict[str, str] = {}
    current_bdf: Optional[str] = None
    current_lines: list[str] = []

    for line in lspci_text.splitlines():
        header = BDF_HEADER_RE.match(line)
        if header:
            if current_bdf is not None:
                blocks[current_bdf] = "\n".join(current_lines)
            current_bdf = header.group("bdf").lower()
            current_lines = [line]
            continue
        if current_bdf is not None:
            current_lines.append(line)

    if current_bdf is not None:
        blocks[current_bdf] = "\n".join(current_lines)
    return blocks


def _normalize_hex_id(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    return value.lower()


def _link_training_from_lnksta(speed_lt: Optional[str], width_lt: Optional[str]) -> Optional[str]:
    parts = [part for part in (speed_lt, width_lt) if part]
    if not parts:
        return None
    if all(part.lower() == "ok" for part in parts):
        return "ok"
    return ",".join(parts)


def parse_lspci_device_block(bdf: str, block: str) -> PcieInventoryDevice:
    """Parse one lspci device block into an inventory record.
    Args:
        bdf: Device BDF address.
        block: Text block for the device from lspci output.
    Returns:
        Parsed inventory device record.
    """
    header = BDF_HEADER_RE.match(block.splitlines()[0])
    device_type = header.group("type").strip() if header else None
    description = header.group("desc").strip() if header else None

    vendor: Optional[str] = None
    device: Optional[str] = None
    revision: Optional[str] = None
    if header:
        ids = VENDOR_DEVICE_RE.search(header.group("desc"))
        if ids:
            vendor = _normalize_hex_id(ids.group("vendor"))
            device = _normalize_hex_id(ids.group("device"))
        rev = REVISION_RE.search(header.group("desc"))
        if rev:
            revision = _normalize_hex_id(rev.group("revision"))

    subvendor: Optional[str] = None
    subdevice: Optional[str] = None
    control: Optional[str] = None
    status: Optional[str] = None
    irq: Optional[str] = None
    driver: Optional[str] = None
    speed: Optional[str] = None
    width: Optional[str] = None
    link_training: Optional[str] = None
    lnkctl: Optional[str] = None
    lnksta: Optional[str] = None
    lnkctl2: Optional[str] = None
    lnksta2: Optional[str] = None
    slot: Optional[str] = None

    for line in block.splitlines():
        sub = SUBSYSTEM_RE.match(line)
        if sub:
            subvendor = _normalize_hex_id(sub.group("subvendor"))
            subdevice = _normalize_hex_id(sub.group("subdevice"))
            continue
        ctl = CONTROL_RE.match(line)
        if ctl:
            control = ctl.group("control").strip()
            continue
        sta = STATUS_RE.match(line)
        if sta:
            status = sta.group("status").strip()
            continue
        irq_match = IRQ_RE.match(line)
        if irq_match:
            irq = irq_match.group("irq")
            continue
        drv = DRIVER_RE.match(line)
        if drv:
            driver = drv.group("driver")
            continue
        lnksta_match = LNKSTA_RE.match(line)
        if lnksta_match:
            speed = lnksta_match.group("speed").strip()
            width = lnksta_match.group("width").strip()
            link_training = _link_training_from_lnksta(
                lnksta_match.group("speed_lt"),
                lnksta_match.group("width_lt"),
            )
            lnksta = line.split(":", 1)[-1].strip()
            continue
        lnkctl_match = LNKCTL_RE.match(line)
        if lnkctl_match:
            lnkctl = lnkctl_match.group("lnkctl").strip()
            continue
        lnksta2_match = LNKSTA2_RE.match(line)
        if lnksta2_match:
            lnksta2 = lnksta2_match.group("lnksta2").strip()
            continue
        lnkctl2_match = LNKCTL2_RE.match(line)
        if lnkctl2_match:
            lnkctl2 = lnkctl2_match.group("lnkctl2").strip()
            continue
        slot_match = SLOT_RE.match(line)
        if slot_match:
            slot = slot_match.group("slot").strip()

    return PcieInventoryDevice(
        address=bdf,
        type=device_type,
        description=description,
        vendor=vendor,
        device=device,
        subvendor=subvendor,
        subdevice=subdevice,
        revision=revision,
        driver=driver,
        speed=speed,
        width=width,
        link_training=link_training,
        slot=slot,
        lnkctl=lnkctl,
        lnksta=lnksta,
        lnkctl2=lnkctl2,
        lnksta2=lnksta2,
        irq=irq,
        control=control,
        status=status,
    )


def parse_lspci_inventory(lspci_text: str) -> PcieInventory:
    """Parse lspci -D -xx -vv output into a BOM-style inventory model.
    Args:
        lspci_text: Raw lspci output text.
    Returns:
        Inventory with total_count and per-BDF device records.
    """
    devices: Dict[BdfStr, PcieInventoryDevice] = {}
    for bdf, block in split_lspci_device_blocks(lspci_text).items():
        devices[bdf] = parse_lspci_device_block(bdf, block)
    return PcieInventory(total_count=len(devices), devices=devices)


def apply_driver_versions(
    inventory: PcieInventory,
    driver_versions: Dict[str, str],
) -> PcieInventory:
    """Attach modinfo driver_version values to inventory devices.
    Args:
        inventory: Parsed inventory to update.
        driver_versions: Mapping of driver name to version string.
    Returns:
        Updated inventory instance.
    """
    updated_devices: Dict[BdfStr, PcieInventoryDevice] = {}
    for bdf, device in inventory.devices.items():
        driver_version = None
        if device.driver:
            driver_version = driver_versions.get(device.driver)
        updated_devices[bdf] = device.model_copy(
            update={"driver_version": driver_version},
        )
    return inventory.model_copy(update={"devices": updated_devices})


_HEX_INVENTORY_FIELDS = frozenset({"vendor", "device", "subvendor", "subdevice", "revision"})


def normalize_inventory_value(field: str, value: str) -> str:
    """Normalize an inventory field value for comparison.
    Args:
        field: Inventory field name.
        value: Raw expected or actual value.
    Returns:
        Normalized string for equality comparison.
    """
    normalized = value.strip()
    if field in _HEX_INVENTORY_FIELDS:
        return normalized.lower().removeprefix("0x")
    return normalized


def inventory_field_value(device: PcieInventoryDevice, field: str) -> Optional[str]:
    """Return a normalized inventory field value from a device record.
    Args:
        device: Inventory device record.
        field: Field name to read.
    Returns:
        Normalized value, or None when the field is unset.
    """
    raw = device.model_dump(mode="json").get(field)
    if raw is None or raw == "":
        return None
    return normalize_inventory_value(field, str(raw))


def filter_inventory_fields(
    device: PcieInventoryDevice,
    fields: Iterable[str],
) -> Dict[str, str]:
    """Return selected non-empty inventory fields from a device record.
    Args:
        device: Inventory device record.
        fields: Field names to include when present.
    Returns:
        Dict of field name to string value.
    """
    payload = device.model_dump(mode="json")
    out: Dict[str, str] = {}
    for field in fields:
        value = payload.get(field)
        if value is not None and value != "":
            out[field] = str(value)
    return out
