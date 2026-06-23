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
"""Shared dummy values for serviceability unit tests (not production data)."""

from __future__ import annotations

from typing import Any

DUMMY_AFID_A = 9001
DUMMY_AFID_B = 9002
DUMMY_AFID_C = 9003
DUMMY_AFID_BELOW_RF = 22
DUMMY_AFID_FATAL_HBM = 25
DUMMY_RF_CPER_AFID = 10000
DUMMY_SERVICE_ACTION_NUM = 99
DUMMY_SERVICE_ACTION_TITLE = "Dummy service action"
DUMMY_UNIT_A = "dummy_unit_a"
DUMMY_UNIT_B = "dummy_unit_b"
DUMMY_UNIT_C = "dummy_unit_c"
DUMMY_DESIGNATION_A = "DUMMY_SLOT_A"
DUMMY_DESIGNATION_B = "DUMMY_SLOT_B"
DUMMY_EVENT_URI = "/redfish/v1/Systems/Dummy/LogServices/DummyEventLog/Entries"
DUMMY_EVENT_URI_ALT = "/redfish/v1/Systems/Dummy/LogServices/DummyEventLog/EntriesAlt"
DUMMY_EVENT_LOG_BASE = "/redfish/v1/Systems/Dummy/LogServices/DummyEventLog"
DUMMY_CPER_ATTACHMENT_URI_1 = f"{DUMMY_EVENT_LOG_BASE}/Attachments/1"
DUMMY_CPER_ATTACHMENT_URI_2 = f"{DUMMY_EVENT_LOG_BASE}/Attachments/2"
DUMMY_TIMESTAMP = "2000-01-01T12:00:00+00:00"
DUMMY_TIMESTAMP_EARLIER = "1999-12-31T12:00:00+00:00"
DUMMY_TIMESTAMP_LATER = "2000-01-02T12:00:00+00:00"
DUMMY_RF_EVENT_COUNT = 2
DUMMY_SAG_PID = "dummy-sag-pid"
DUMMY_SAG_REVISION = "dummy-rev-0"
DUMMY_HUB_VERSION = "0.0.0-dummy"
DUMMY_BMC_HOST = "dummy-bmc.example"
DUMMY_OEM_VENDOR = "DummyVendor"
DUMMY_GPU_SERIAL_NUMBER = "DUMMY-GPU-SERIAL-0001"
DUMMY_DECODED_ERROR_TYPE = "dummy_error_type"
DUMMY_RF_EVENT_ID_1 = "dummy-rf-evt-1"
DUMMY_RF_EVENT_ID_2 = "dummy-rf-evt-2"
DUMMY_CPER_EVENT_ID_BASIC = "dummy-cper-evt-1"
DUMMY_CPER_EVENT_ID_SKIP = "dummy-cper-evt-skip"
DUMMY_CPER_EVENT_ID_RF = "dummy-cper-evt-rf"
DUMMY_CPER_BYTES_BASIC = b"\x01\x02dummy-cper"
DUMMY_CPER_BYTES_RF = b"\xaa\xbb"


def dummy_chassis_uri(unit: str) -> str:
    return f"/redfish/v1/Chassis/{unit}"


def dummy_aca_err_row(*, serial: bool = True, decoded: bool = True) -> dict[str, Any]:
    meta = {"SerialNumber": DUMMY_GPU_SERIAL_NUMBER} if serial else {"GpuFw": "dummy-fw"}
    decoded_data = {"error_type": DUMMY_DECODED_ERROR_TYPE} if decoded else {}
    return {"DecodedData": decoded_data, "MetaData": meta}


def dummy_cper_rf_member() -> dict[str, Any]:
    """RF-range AFID with ACA decode + serial (CPER attachment fetch expected)."""
    return {
        "Id": DUMMY_CPER_EVENT_ID_RF,
        "Created": DUMMY_TIMESTAMP_LATER,
        "CPER": {"NotificationType": "dummy-notification-type"},
        "DiagnosticDataType": "CPER",
        "AdditionalDataURI": DUMMY_CPER_ATTACHMENT_URI_2,
        "Oem": {
            "AMDFieldIdentifiers": [{"AFID": DUMMY_RF_CPER_AFID}],
            "ErrDataArr": [dummy_aca_err_row()],
        },
    }


def dummy_cper_skip_member() -> dict[str, Any]:
    """Low AFID with ACA decode + serial (CPER attachment fetch skipped)."""
    return {
        "Id": DUMMY_CPER_EVENT_ID_SKIP,
        "Created": DUMMY_TIMESTAMP_LATER,
        "CPER": {"NotificationType": "dummy-notification-type"},
        "DiagnosticDataType": "CPER",
        "AdditionalDataURI": DUMMY_CPER_ATTACHMENT_URI_1,
        "Oem": {
            "AMDFieldIdentifiers": [{"AFID": DUMMY_AFID_BELOW_RF}],
            "ErrDataArr": [
                {
                    "DecodedData": {"error_type": "dummy_on_die_ecc"},
                    "MetaData": {"SerialNumber": DUMMY_GPU_SERIAL_NUMBER},
                }
            ],
        },
    }


def dummy_cper_basic_member() -> dict[str, Any]:
    """CPER event without OEM ACA block (attachment fetch expected)."""
    return {
        "Id": DUMMY_CPER_EVENT_ID_BASIC,
        "Created": DUMMY_TIMESTAMP_LATER,
        "CPER": {"NotificationType": "dummy-notification-type"},
        "DiagnosticDataType": "CPER",
        "AdditionalDataURI": DUMMY_CPER_ATTACHMENT_URI_1,
    }


def dummy_openbmc_log_entry() -> dict[str, Any]:
    """OpenBMC-style LogEntry with Links OOC and AMDFieldIdentifiers[]."""
    return {
        "@odata.id": f"{DUMMY_EVENT_URI}/1",
        "Created": DUMMY_TIMESTAMP,
        "Id": DUMMY_RF_EVENT_ID_1,
        "Links": {
            "OriginOfCondition": {"@odata.id": dummy_chassis_uri(DUMMY_UNIT_A)},
        },
        "Oem": {
            "AMDFieldIdentifiers": [
                {
                    "AFID": DUMMY_AFID_BELOW_RF,
                    "Description": "dummy on-die ECC, uncorrected, non-fatal",
                    "ServiceableUnits": [{"@odata.id": dummy_chassis_uri(DUMMY_UNIT_A)}],
                    "ServiceableUnits@odata.count": 1,
                }
            ],
            "AMDFieldIdentifiers@Members.count": 1,
        },
    }


def dummy_openbmc_log_entry_serviceable_units_only() -> dict[str, Any]:
    """LogEntry with ServiceableUnits only (no Links OOC)."""
    return {
        "Created": DUMMY_TIMESTAMP,
        "Oem": {
            "AMDFieldIdentifiers": [
                {
                    "AFID": DUMMY_AFID_A,
                    "ServiceableUnits": [{"@odata.id": dummy_chassis_uri(DUMMY_UNIT_B)}],
                }
            ],
        },
    }


def dummy_fatal_hbm_log_entry() -> dict[str, Any]:
    """Minimal CPER-style row with Links + AMDFieldIdentifiers[]."""
    return {
        "Created": DUMMY_TIMESTAMP_LATER,
        "Id": DUMMY_RF_EVENT_ID_2,
        "Links": {
            "OriginOfCondition": {"@odata.id": dummy_chassis_uri(DUMMY_UNIT_C)},
        },
        "Oem": {
            "AMDFieldIdentifiers": [
                {
                    "AFID": DUMMY_AFID_FATAL_HBM,
                    "Description": "dummy fatal HBM",
                    "ServiceableUnits": [{"@odata.id": dummy_chassis_uri(DUMMY_UNIT_C)}],
                    "ServiceableUnits@odata.count": 1,
                }
            ],
            "AMDFieldIdentifiers@Members.count": 1,
        },
    }
