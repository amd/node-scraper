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

from framework.common.serviceability_dummy_data import (
    DUMMY_AFID_A,
    DUMMY_FRU_PRIMARY_NORM,
    DUMMY_FRU_SECONDARY_NORM,
    DUMMY_RF_EVENT_COUNT_SAMPLE,
    DUMMY_TIMESTAMP,
    DUMMY_TIMESTAMP_LATER,
    DUMMY_UNIT_A,
    DUMMY_UNIT_B,
    dummy_sag_for_fru_tests,
)

from nodescraper.plugins.serviceability.afid_sag_lookup import (
    format_collected_afid_fru_summary_lines,
    group_afid_events_by_fru,
    known_fru_names_from_sag,
)
from nodescraper.plugins.serviceability.se_models import AfidEvent


def test_group_afid_events_by_fru_and_missing_fru_report():
    sag_data = dummy_sag_for_fru_tests()
    events = [
        AfidEvent(afid=DUMMY_AFID_A, serviceable_unit=DUMMY_UNIT_A, time=DUMMY_TIMESTAMP),
        AfidEvent(afid=DUMMY_AFID_A, serviceable_unit=DUMMY_UNIT_B, time=DUMMY_TIMESTAMP_LATER),
    ]
    grouped = group_afid_events_by_fru(events, sag_data)
    assert DUMMY_FRU_PRIMARY_NORM in grouped
    assert len(grouped[DUMMY_FRU_PRIMARY_NORM]) == 2
    lines = format_collected_afid_fru_summary_lines(
        events,
        sag_data,
        rf_event_count=DUMMY_RF_EVENT_COUNT_SAMPLE,
    )
    assert any(DUMMY_FRU_PRIMARY_NORM in line for line in lines)
    assert any(DUMMY_FRU_SECONDARY_NORM in line for line in lines)
    assert known_fru_names_from_sag(sag_data) == [
        DUMMY_FRU_PRIMARY_NORM,
        DUMMY_FRU_SECONDARY_NORM,
    ]
