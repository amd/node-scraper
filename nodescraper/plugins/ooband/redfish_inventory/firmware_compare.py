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
from typing import Any, Optional, TypedDict

from .inventory_data import RedfishInventoryDataModel

_FIRMWARE_MEMBER = "/FirmwareInventory/"


class FirmwareComponent(TypedDict):
    """Firmware fields recorded for one FirmwareInventory member."""

    version: str
    health: str
    state: str
    software_id: str
    updateable: str
    svn: str


class FirmwareMismatch(TypedDict):
    """One firmware id whose version or presence is not the same on every target."""

    firmware_id: str
    targets: dict[str, Optional[FirmwareComponent]]


def _text_or_na(value: Any) -> str:
    """Return a display string, using N/A when the value is missing.

    Args:
        value: Field value from a firmware member.

    Returns:
        The string value, or N/A when value is None or empty.
    """
    if value is None or value == "":
        return "N/A"
    return str(value)


def _member_name(path: str) -> str:
    """Return the FirmwareInventory member name from a Redfish path.

    Args:
        path: Collected resource path.

    Returns:
        The member name, or an empty string for collections and nested resources.
    """
    clean = path.split("?", 1)[0].rstrip("/")
    if _FIRMWARE_MEMBER not in clean:
        return ""
    tail = clean.split(_FIRMWARE_MEMBER, 1)[1]
    if not tail or "/" in tail:
        return ""
    return tail


def _component(body: dict) -> FirmwareComponent:
    """Read the firmware fields stored for one member.

    Args:
        body: FirmwareInventory member payload.

    Returns:
        Version, health, state, software id, updateable, and SVN.
    """
    status = body.get("Status")
    if not isinstance(status, dict):
        status = {}
    oem = body.get("Oem")
    if not isinstance(oem, dict):
        oem = {}
    updateable = body.get("Updateable")
    svn = oem.get("SVN")
    return {
        "version": _text_or_na(body.get("Version")),
        "health": _text_or_na(status.get("Health")),
        "state": _text_or_na(status.get("State")),
        "software_id": _text_or_na(body.get("SoftwareId")),
        "updateable": "N/A" if updateable is None else str(updateable),
        "svn": "" if svn is None else str(svn),
    }


def firmware_components(
    model: RedfishInventoryDataModel,
) -> dict[str, FirmwareComponent]:
    """Return FirmwareInventory members keyed by their raw id.

    Args:
        model: Inventory collected from one target.

    Returns:
        Firmware id to the recorded fields. A missing version is N/A.
    """
    components: dict[str, FirmwareComponent] = {}
    for path, body in model.responses.items():
        if not isinstance(path, str) or not isinstance(body, dict):
            continue
        member = _member_name(path)
        if not member:
            continue
        raw_id = body.get("Id")
        if isinstance(raw_id, str) and raw_id.strip():
            fw_id = raw_id.strip()
        else:
            fw_id = member
        components[fw_id] = _component(body)
    return components


def firmware_mismatches(
    by_target: dict[str, dict[str, FirmwareComponent]],
) -> list[FirmwareMismatch]:
    """Find firmware ids whose version or presence differs across targets.

    Args:
        by_target: Target key to that target's firmware members.

    Returns:
        Mismatches in firmware-id order. An absent member is included.
    """
    names: set[str] = set()
    for components in by_target.values():
        names.update(components)
    mismatches: list[FirmwareMismatch] = []
    for fw_id in sorted(names):
        rows: dict[str, Optional[FirmwareComponent]] = {}
        versions: list[str] = []
        missing = False
        for target in sorted(by_target):
            record = by_target[target].get(fw_id)
            rows[target] = record
            if record is None:
                missing = True
            else:
                versions.append(record["version"])
        if missing or len(set(versions)) > 1:
            mismatches.append({"firmware_id": fw_id, "targets": rows})
    return mismatches


def firmware_target_text(record: Optional[FirmwareComponent]) -> str:
    """Format one target's firmware fields for a warning.

    Args:
        record: Fields for this target, or None when the member is absent.

    Returns:
        missing, or the version and the other recorded fields.
    """
    if record is None:
        return "missing"
    return (
        f"version={record['version']} health={record['health']} "
        f"state={record['state']} software_id={record['software_id']} "
        f"updateable={record['updateable']} svn={record['svn']}"
    )
