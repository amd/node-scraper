###############################################################################
#
# MIT License
#
# Copyright (c) 2026 Advanced Micro Devices, Inc.
#
###############################################################################
"""AFID / serviceable unit extraction for OpenBMC-style LogEntry payloads."""
from __future__ import annotations

from nodescraper.plugins.serviceability.afid_events import (
    _afid_event_from_rf_member,
    build_afid_events_from_data,
)
from nodescraper.plugins.serviceability.serviceability_data import (
    ServiceabilityDataModel,
)

# Shape from after_clear_rma_case.json: AFID under Oem.AMDFieldIdentifiers[], OOC under Links.
_SAMPLE_LOG_ENTRY = {
    "@odata.id": "/redfish/v1/Systems/UBB/LogServices/EventLog/Entries/1",
    "Created": "2026-06-16T20:25:22+00:00",
    "Id": "1",
    "Links": {
        "OriginOfCondition": {
            "@odata.id": "/redfish/v1/Chassis/OAM_7",
        }
    },
    "Oem": {
        "AMDFieldIdentifiers": [
            {
                "AFID": 22,
                "Description": "On-die ECC, Uncorrected, Non-fatal",
                "ServiceableUnits": [
                    {"@odata.id": "/redfish/v1/Chassis/OAM_7"},
                ],
                "ServiceableUnits@odata.count": 1,
            }
        ],
        "AMDFieldIdentifiers@Members.count": 1,
    },
}


def test_afid_event_from_openbmc_log_entry_with_links_and_amd_field_identifiers():
    ev = _afid_event_from_rf_member(_SAMPLE_LOG_ENTRY)
    assert ev is not None
    assert ev.afid == 22
    assert ev.serviceable_unit == "OAM_7"
    assert "2026-06-16" in ev.time


def test_serviceable_unit_from_oem_serviceable_units_when_no_links():
    member = {
        "Created": "2026-06-16T20:25:22+00:00",
        "Oem": {
            "AMDFieldIdentifiers": [
                {
                    "AFID": 23,
                    "ServiceableUnits": [
                        {"@odata.id": "/redfish/v1/Chassis/OAM_3"},
                    ],
                }
            ],
        },
    }
    ev = _afid_event_from_rf_member(member)
    assert ev is not None
    assert ev.afid == 23
    assert ev.serviceable_unit == "OAM_3"


# Minimal slice of smci350 command_artifacts.json first CPER row (Links + AMDFieldIdentifiers[]).
_SMCI350_STYLE_ENTRY = {
    "Created": "2026-06-16T18:53:21+00:00",
    "Id": "1",
    "Links": {
        "OriginOfCondition": {"@odata.id": "/redfish/v1/Chassis/OAM_2"},
    },
    "Oem": {
        "AMDFieldIdentifiers": [
            {
                "AFID": 25,
                "Description": "All Other HBM, Fatal",
                "ServiceableUnits": [{"@odata.id": "/redfish/v1/Chassis/OAM_2"}],
                "ServiceableUnits@odata.count": 1,
            }
        ],
        "AMDFieldIdentifiers@Members.count": 1,
    },
}


def test_afid_event_smci350_style_fatal_hbm_entry():
    ev = _afid_event_from_rf_member(_SMCI350_STYLE_ENTRY)
    assert ev is not None
    assert ev.afid == 25
    assert ev.serviceable_unit == "OAM_2"


def test_build_afid_events_from_data_includes_openbmc_entries():
    data = ServiceabilityDataModel(
        rf_events=[_SAMPLE_LOG_ENTRY, _SMCI350_STYLE_ENTRY],
        cper_data={},
    )
    events = build_afid_events_from_data(data)
    assert len(events) == 2
    by_afid_oam = {(e.afid, e.serviceable_unit) for e in events}
    assert (22, "OAM_7") in by_afid_oam
    assert (25, "OAM_2") in by_afid_oam
