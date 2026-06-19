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

# Redfish CPER (RF) style AFIDs start at this value; lower values are in-band /
# OEM-field AFIDs already reflected on the log entry.
RF_CPER_AFID_MIN = 10000

_SERIAL_KEYS = ("SerialNumber", "serial_number", "UbbSerial", "ubb_serial")


def event_afids_from_oem(event: dict[str, Any]) -> list[int]:
    """AFIDs from ``Oem.AMDFieldIdentifiers`` (or similar list-of-dicts)."""
    oem = event.get("Oem")
    if not isinstance(oem, dict):
        return []
    raw = oem.get("AMDFieldIdentifiers")
    if not isinstance(raw, list):
        return []
    out: list[int] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        for key in ("AFID", "Afid", "afid"):
            if key in item and item[key] is not None:
                try:
                    out.append(int(item[key]))
                except (TypeError, ValueError):
                    pass
                break
    return out


def _err_data_arr_entries(event: dict[str, Any]) -> list[dict[str, Any]]:
    oem = event.get("Oem")
    if not isinstance(oem, dict):
        return []
    arr = oem.get("ErrDataArr")
    if not isinstance(arr, list):
        return []
    return [e for e in arr if isinstance(e, dict)]


def event_has_aca_decode(event: dict[str, Any]) -> bool:
    """True when the log entry includes ACA-style ``DecodedData`` under ``ErrDataArr``."""
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
    """Serial (or UBB serial) present on any ``ErrDataArr`` row (typically ``MetaData``)."""
    for entry in _err_data_arr_entries(event):
        meta = entry.get("MetaData")
        if _nonempty_serial_in_mapping(meta):
            return True
        decoded = entry.get("DecodedData")
        if _nonempty_serial_in_mapping(decoded):
            return True
    return False


def should_skip_cper_fetch_or_decode(event: dict[str, Any]) -> bool:
    """Whether to omit CPER binary fetch and configured CPER decode for this Redfish member.

    Skip when:

    * Every OEM-listed AFID is below ``RF_CPER_AFID_MIN`` (non-RF CPER range),
      ACA ``DecodedData`` is present, and a serial is present on the entry; or
    * ACA ``DecodedData`` is present but no serial — the CPER blob does not add
      actionable identity beyond what is already missing from the log.
    """
    if not event_has_aca_decode(event):
        return False
    if not event_aca_includes_serial(event):
        return True
    afids = event_afids_from_oem(event)
    if not afids:
        return False
    return all(afid < RF_CPER_AFID_MIN for afid in afids)
