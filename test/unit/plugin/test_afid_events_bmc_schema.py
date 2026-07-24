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

from framework.common.serviceability_dummy_data import (
    DUMMY_AFID_A,
    DUMMY_AFID_BELOW_RF,
    DUMMY_AFID_FATAL_HBM,
    DUMMY_NESTED_OEM_AFID,
    DUMMY_TIMESTAMP,
    DUMMY_UNIT_A,
    DUMMY_UNIT_B,
    DUMMY_UNIT_C,
    DUMMY_UNIT_NESTED,
    dummy_fatal_hbm_log_entry,
    dummy_helios_sensor_log_entry,
    dummy_openbmc_log_entry,
    dummy_openbmc_log_entry_serviceable_units_only,
)

from nodescraper.plugins.serviceability.afid_events import (
    _afid_event_from_rf_member,
    build_afid_events_from_data,
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


def test_afid_event_nested_oem_amd_log_entry():
    ev = _afid_event_from_rf_member(dummy_helios_sensor_log_entry())
    assert ev is not None
    assert ev.afid == DUMMY_NESTED_OEM_AFID
    assert ev.serviceable_unit == DUMMY_UNIT_NESTED
    assert ev.time.startswith(DUMMY_TIMESTAMP[:10])


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
