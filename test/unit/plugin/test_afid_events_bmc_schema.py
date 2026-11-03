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
"""AFID / serviceable unit extraction for OpenBMC-style LogEntry payloads."""

from __future__ import annotations

from serviceability_dummy_data import (
    DUMMY_AFID_A,
    DUMMY_AFID_BELOW_RF,
    DUMMY_AFID_FATAL_HBM,
    DUMMY_TIMESTAMP,
    DUMMY_UNIT_A,
    DUMMY_UNIT_B,
    DUMMY_UNIT_C,
    dummy_fatal_hbm_log_entry,
    dummy_openbmc_log_entry,
    dummy_openbmc_log_entry_serviceable_units_only,
)

from nodescraper.plugins.serviceability.afid_events import (
    _afid_event_from_rf_member,
    amd_field_identifiers_with_units,
    build_afid_events_from_data,
)
from nodescraper.plugins.serviceability.se_runner import (
    drop_afids_without_serviceable_units,
)
from nodescraper.plugins.serviceability.serviceability_data import (
    ServiceabilityDataModel,
)


def test_afid_event_from_openbmc_log_entry_with_links_and_amd_field_identifiers():
    ev = _afid_event_from_rf_member(dummy_openbmc_log_entry())
    assert ev is not None
    assert ev.afid == DUMMY_AFID_BELOW_RF
    assert ev.serviceable_unit == DUMMY_UNIT_A
    assert DUMMY_TIMESTAMP[:10] in ev.time


def test_serviceable_unit_from_oem_serviceable_units_when_no_links():
    ev = _afid_event_from_rf_member(dummy_openbmc_log_entry_serviceable_units_only())
    assert ev is not None
    assert ev.afid == DUMMY_AFID_A
    assert ev.serviceable_unit == DUMMY_UNIT_B


def test_afid_event_fatal_hbm_log_entry():
    ev = _afid_event_from_rf_member(dummy_fatal_hbm_log_entry())
    assert ev is not None
    assert ev.afid == DUMMY_AFID_FATAL_HBM
    assert ev.serviceable_unit == DUMMY_UNIT_C


def test_build_afid_events_from_data_includes_openbmc_entries():
    data = ServiceabilityDataModel(
        rf_events=[dummy_openbmc_log_entry(), dummy_fatal_hbm_log_entry()],
        cper_data={},
    )
    events = build_afid_events_from_data(data)
    assert len(events) == 2
    by_afid_oam = {(e.afid, e.serviceable_unit) for e in events}
    assert (DUMMY_AFID_BELOW_RF, DUMMY_UNIT_A) in by_afid_oam
    assert (DUMMY_AFID_FATAL_HBM, DUMMY_UNIT_C) in by_afid_oam


def test_amd_field_identifiers_split_and_drop_members_without_a_location():
    located = {
        "Id": "located",
        "Oem": {
            "AMD": {
                "AMDFieldIdentifiers": [
                    {
                        "AFID": DUMMY_AFID_A,
                        "ServiceableUnits": [{"@odata.id": f"/redfish/v1/Chassis/{DUMMY_UNIT_B}"}],
                    }
                ]
            }
        },
    }
    missing = {
        "@odata.id": "/redfish/v1/Systems/dummy/LogServices/EventLog/Entries/9",
        "Id": "missing",
        "Oem": {"AMD": {"AMDFieldIdentifiers": [{"AFID": 11045, "Description": "update"}]}},
    }
    mixed = {
        "Id": "mixed",
        "Oem": {
            "AMD": {
                "AMDFieldIdentifiers": [
                    {"AFID": 11045},
                    {
                        "AFID": DUMMY_AFID_A,
                        "ServiceableUnits": [{"@odata.id": f"/redfish/v1/Chassis/{DUMMY_UNIT_A}"}],
                    },
                ]
            }
        },
    }
    plain = {"Id": "plain", "Message": "no oem"}
    usable, unusable = amd_field_identifiers_with_units(missing["Oem"])
    assert usable == []
    assert unusable == [{"AFID": 11045, "Description": "update"}]
    assert amd_field_identifiers_with_units(plain) is None
    kept = drop_afids_without_serviceable_units([located, missing, mixed, plain])
    kept_ids = [member["Id"] for member in kept]
    assert kept_ids == ["located", "mixed", "plain"]
    mixed_kept = next(member for member in kept if member["Id"] == "mixed")
    assert mixed_kept["Oem"]["AMD"]["AMDFieldIdentifiers"] == [
        {
            "AFID": DUMMY_AFID_A,
            "ServiceableUnits": [{"@odata.id": f"/redfish/v1/Chassis/{DUMMY_UNIT_A}"}],
        }
    ]


def test_ok_severity_without_serviceable_units_is_silent(caplog):
    member = {
        "Id": "ok-update",
        "@odata.id": "/redfish/v1/Systems/dummy/LogServices/EventLog/Entries/1",
        "Severity": "OK",
        "Oem": {"AMD": {"AMDFieldIdentifiers": [{"AFID": 11045}]}},
    }
    with caplog.at_level("WARNING"):
        kept = drop_afids_without_serviceable_units([member])
    assert kept == []
    assert "11045" not in caplog.text


def test_non_ok_severity_without_serviceable_units_warns(caplog):
    member = {
        "Id": "fault",
        "@odata.id": "/redfish/v1/Systems/dummy/LogServices/EventLog/Entries/2",
        "Severity": "Critical",
        "Oem": {"AMD": {"AMDFieldIdentifiers": [{"AFID": 11045}]}},
    }
    with caplog.at_level("WARNING"):
        kept = drop_afids_without_serviceable_units([member])
    assert kept == []
    assert "Waiving AFID 11045" in caplog.text


def test_serviceable_unit_from_oem_amd_field_identifiers():
    ev = _afid_event_from_rf_member(
        {
            "Created": DUMMY_TIMESTAMP,
            "Oem": {
                "AMD": {
                    "AMDFieldIdentifiers": [
                        {
                            "AFID": DUMMY_AFID_A,
                            "ServiceableUnits": [
                                {"@odata.id": f"/redfish/v1/Chassis/{DUMMY_UNIT_B}"}
                            ],
                        }
                    ]
                }
            },
        }
    )
    assert ev is not None
    assert ev.afid == DUMMY_AFID_A
    assert ev.serviceable_unit == DUMMY_UNIT_B
