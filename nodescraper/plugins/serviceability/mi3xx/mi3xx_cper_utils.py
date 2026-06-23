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
from __future__ import annotations

from typing import Any

# CPER-method AFIDs <= 34; MI3XX Redfish-method AFIDs 10000–10999.
CPER_METHOD_AFID_MAX = 34
REDFISH_METHOD_AFID_MIN = 10000
REDFISH_METHOD_AFID_MAX = 10999

_SERIAL_KEYS = ("SerialNumber", "serial_number", "UbbSerial", "ubb_serial")


def get_amd_oem_dict(event: dict[str, Any]) -> dict[str, Any]:
    """Return the AMD OEM payload dict for a Redfish log member.

    BMC layouts vary: fields may live on Oem directly or under Oem.AMD.
    When AMD is absent, returns Oem; when present, returns AMD if it is a dict.
    """
    if not isinstance(oem := event.get("Oem"), dict):
        return {}
    if (amd := oem.get("AMD")) is None:
        return oem
    return amd if isinstance(amd, dict) else {}


def _oem_list_field(oem_dict: dict[str, Any], key: str) -> list[Any]:
    """Return a list field from the resolved AMD OEM dict."""
    raw = oem_dict.get(key)
    return raw if isinstance(raw, list) else []


def event_afids_from_oem(event: dict[str, Any]) -> list[int]:
    """AFIDs from Oem.AMDFieldIdentifiers or Oem.AMD.AMDFieldIdentifiers."""
    raw = _oem_list_field(get_amd_oem_dict(event), "AMDFieldIdentifiers")
    out: list[int] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        for key in ("AFID", "Afid", "afid"):
            if (v := item.get(key)) is not None:
                try:
                    out.append(int(v))
                except (TypeError, ValueError):
                    pass
                break
    return out


def _err_data_arr_entries(event: dict[str, Any]) -> list[dict[str, Any]]:
    """ErrDataArr rows from Oem.ErrDataArr or Oem.AMD.ErrDataArr."""
    arr = _oem_list_field(get_amd_oem_dict(event), "ErrDataArr")
    return [e for e in arr if isinstance(e, dict)]


def event_has_aca_decode(event: dict[str, Any]) -> bool:
    """True when the log entry includes ACA-style DecodedData under ErrDataArr."""
    for entry in _err_data_arr_entries(event):
        decoded = entry.get("DecodedData")
        if isinstance(decoded, dict) and decoded:
            return True
    return False


def _nonempty_serial_in_mapping(obj: Any) -> bool:
    if not isinstance(obj, dict):
        return False
    for key in _SERIAL_KEYS:
        val = obj.get(key)
        if val is not None and str(val).strip():
            return True
    return False


def event_aca_includes_serial(event: dict[str, Any]) -> bool:
    """Serial (or UBB serial) present on any ErrDataArr row MetaData."""
    return any(
        _nonempty_serial_in_mapping(entry.get("MetaData")) for entry in _err_data_arr_entries(event)
    )


def is_cper_method_afid(afid: int) -> bool:
    """True for CPER-method AFIDs (<= CPER_METHOD_AFID_MAX), including on RF log entries."""
    return afid <= CPER_METHOD_AFID_MAX


def is_redfish_method_afid(afid: int) -> bool:
    """True for MI3XX Redfish-method AFIDs in the 10k range (10000–10999)."""
    return REDFISH_METHOD_AFID_MIN <= afid <= REDFISH_METHOD_AFID_MAX


def should_skip_cper_fetch_or_decode(event: dict[str, Any]) -> bool:
    """Whether to omit CPER binary fetch and configured CPER decode for this Redfish member.

    Skip when:

    * Every OEM-listed AFID is CPER-method (<= CPER_METHOD_AFID_MAX; may match
      in-band CPER AFIDs), ACA DecodedData is present, and serial is on the entry; or
    * ACA DecodedData is present but no serial — the CPER blob does not add
      actionable identity beyond what is already missing from the log.
    """
    if not event_has_aca_decode(event):
        return False
    if not event_aca_includes_serial(event):
        return True
    afids = event_afids_from_oem(event)
    if not afids:
        return False
    return all(is_cper_method_afid(afid) for afid in afids)
