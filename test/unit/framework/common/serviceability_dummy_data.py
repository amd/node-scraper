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
DUMMY_SAG_VARIANT = "dummy-variant-0"
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
DUMMY_NESTED_OEM_AFID = 9101
DUMMY_UNIT_NESTED = "dummy_nested_unit_0"
DUMMY_FRU_PRIMARY = "DUMMY-FRU-PRIMARY"
DUMMY_FRU_SECONDARY = "DUMMY-FRU-SECONDARY"
DUMMY_FRU_TERTIARY = "DUMMY-FRU-TERTIARY"
DUMMY_FRU_PRIMARY_NORM = "DUMMY_FRU_PRIMARY"
DUMMY_FRU_SECONDARY_NORM = "DUMMY_FRU_SECONDARY"
DUMMY_SERIAL_PRIMARY = "DUMMY-SERIAL-001"
DUMMY_SERIAL_RF_META = "DUMMY-SERIAL-RF-001"
DUMMY_PART_PRIMARY = "DUMMY-PART-001"
DUMMY_PART_RF_META = "DUMMY-PART-RF-001"
DUMMY_UNIT_NAME_PRIMARY = "Dummy unit primary"
DUMMY_UNIT_VERSION_PRIMARY = "0.0.1-dummy"
DUMMY_ERROR_CATEGORY = "DummyErrorCategory"
DUMMY_ERROR_TYPE = "DummyErrorType"
DUMMY_ERROR_SEVERITY = "Critical"
DUMMY_TIER_LABEL = "Secondary"
DUMMY_TIER_CRITICAL = "Critical"
DUMMY_SA_SEVERITY = 20
DUMMY_PRIORITY = 20
DUMMY_AFID_SUMMARY = "DummyErrorCategory / DummyErrorType"
DUMMY_RF_EVENT_COUNT_SAMPLE = 99
DUMMY_MESSAGE_ID = "DummyEvent.1.0.DummyThreshold"
DUMMY_SERVICE_ACTION_NUM_ALT = 88
DUMMY_HUB_VERSION_ENTRY = "0.0.0-dummy-entry"
DUMMY_SERVICE_ACTION_CATEGORY = "DummyCategory"
DUMMY_SERVICE_ACTION_STEP = "Dummy step."


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


def dummy_nested_oem_amd_log_entry() -> dict[str, Any]:
    """LogEntry with Oem.AMD.AMDFieldIdentifiers and Links OOC (nested OEM layout)."""
    return {
        "Created": DUMMY_TIMESTAMP,
        "Id": "dummy-nested-oem-1",
        "Links": {
            "OriginOfCondition": {"@odata.id": dummy_chassis_uri(DUMMY_UNIT_NESTED)},
        },
        "MessageId": DUMMY_MESSAGE_ID,
        "Oem": {
            "AMD": {
                "@odata.type": "#Dummy_Message.v1_0_0.Dummy_Message",
                "AMDFieldIdentifiers": [
                    {
                        "AFID": DUMMY_NESTED_OEM_AFID,
                        "Description": "dummy nested OEM sensor error",
                        "ServiceableUnits": [{"@odata.id": dummy_chassis_uri(DUMMY_UNIT_NESTED)}],
                        "ServiceableUnits@odata.count": 1,
                    }
                ],
                "AMDFieldIdentifiers@Members.count": 1,
            }
        },
        "Severity": DUMMY_ERROR_SEVERITY,
    }


dummy_helios_sensor_log_entry = dummy_nested_oem_amd_log_entry


def dummy_sag_for_fru_tests() -> dict[str, Any]:
    """Minimal SAG with two FRUs and AFID mappings for FRU grouping tests."""
    return {
        "serviceable_fru": [
            {DUMMY_FRU_PRIMARY.lower(): 1},
            {DUMMY_FRU_SECONDARY.lower(): 5},
        ],
        "afid": {
            str(DUMMY_AFID_A): {"fru": DUMMY_FRU_PRIMARY},
            str(DUMMY_AFID_B): {"fru": DUMMY_FRU_SECONDARY},
        },
        "service_actions": {
            str(DUMMY_SERVICE_ACTION_NUM): {
                "title": DUMMY_SERVICE_ACTION_TITLE,
                "category": DUMMY_SERVICE_ACTION_CATEGORY,
                "severity": DUMMY_SA_SEVERITY,
                "steps": [{"step_num": 0, "description": DUMMY_SERVICE_ACTION_STEP}],
            }
        },
    }


def dummy_sag_for_csv_tests() -> dict[str, Any]:
    """SAG with three FRUs for CSV empty-row coverage."""
    return {
        "serviceable_fru": [
            {DUMMY_FRU_PRIMARY: {}},
            {DUMMY_FRU_SECONDARY: {}},
            {DUMMY_FRU_TERTIARY: {}},
        ],
        "afid": {
            str(DUMMY_AFID_A): {
                "error_category": DUMMY_ERROR_CATEGORY,
                "error_type": DUMMY_ERROR_TYPE,
                "error_severity": DUMMY_ERROR_SEVERITY,
                "fru": DUMMY_FRU_PRIMARY,
                "priority": DUMMY_PRIORITY,
                "service_action_num": DUMMY_SERVICE_ACTION_NUM,
            }
        },
        "service_actions": {
            str(DUMMY_SERVICE_ACTION_NUM): {
                "title": DUMMY_SERVICE_ACTION_TITLE,
                "severity": DUMMY_SA_SEVERITY,
            },
        },
    }


def dummy_nested_oem_rf_member(*, unit: str = DUMMY_UNIT_A) -> dict[str, Any]:
    """Redfish member with nested Oem.AMD.AMDFieldIdentifiers for CSV identity tests."""
    return {
        "Created": DUMMY_TIMESTAMP,
        "Oem": {
            "AMD": {
                "AMDFieldIdentifiers": [
                    {
                        "AFID": DUMMY_AFID_A,
                        "ServiceableUnits": [{"@odata.id": dummy_chassis_uri(unit)}],
                    }
                ],
                "ErrDataArr": [
                    {
                        "MetaData": {
                            "SerialNumber": DUMMY_SERIAL_RF_META,
                            "PartNumber": DUMMY_PART_RF_META,
                        }
                    }
                ],
            }
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
