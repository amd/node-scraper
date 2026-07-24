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
    DUMMY_AFID_SUMMARY,
    DUMMY_ERROR_SEVERITY,
    DUMMY_FRU_PRIMARY,
    DUMMY_FRU_SECONDARY,
    DUMMY_FRU_TERTIARY,
    DUMMY_PART_PRIMARY,
    DUMMY_SA_SEVERITY,
    DUMMY_SERIAL_PRIMARY,
    DUMMY_SERVICE_ACTION_NUM,
    DUMMY_SERVICE_ACTION_TITLE,
    DUMMY_TIER_LABEL,
    DUMMY_TIMESTAMP,
    DUMMY_UNIT_A,
    DUMMY_UNIT_NAME_PRIMARY,
    DUMMY_UNIT_VERSION_PRIMARY,
    dummy_nested_oem_rf_member,
    dummy_sag_for_csv_tests,
)

from nodescraper.plugins.serviceability.afid_fru_csv import (
    AFID_FRU_CSV_COLUMNS,
    build_afid_fru_csv_rows,
)
from nodescraper.plugins.serviceability.se_models import (
    AfidEvent,
    HubTriageResult,
    ServiceabilityBlock,
)
from nodescraper.plugins.serviceability.serviceability_data import (
    DeviceInfo,
    ServiceabilityDataModel,
)


def test_build_afid_fru_csv_rows_includes_empty_fru_rows():
    data = ServiceabilityDataModel(
        afid_events=[
            AfidEvent(afid=DUMMY_AFID_A, serviceable_unit=DUMMY_UNIT_A, time=DUMMY_TIMESTAMP),
        ],
        assembly_info={
            DUMMY_UNIT_A: DeviceInfo(
                name=DUMMY_UNIT_NAME_PRIMARY,
                serial_number=DUMMY_SERIAL_PRIMARY,
                part_number=DUMMY_PART_PRIMARY,
                version=DUMMY_UNIT_VERSION_PRIMARY,
            )
        },
        rf_events=[dummy_nested_oem_rf_member(unit=DUMMY_UNIT_A)],
        serviceability=ServiceabilityBlock(
            hub_triage_results=[
                HubTriageResult(
                    afid=DUMMY_AFID_A,
                    location=DUMMY_UNIT_A,
                    count=1,
                    service_action_num=DUMMY_SERVICE_ACTION_NUM,
                    tier_label=DUMMY_TIER_LABEL,
                    sa_severity=DUMMY_SA_SEVERITY,
                    service_action_title=DUMMY_SERVICE_ACTION_TITLE,
                    afid_summary=DUMMY_AFID_SUMMARY,
                )
            ]
        ),
    )
    rows = build_afid_fru_csv_rows(data, dummy_sag_for_csv_tests())
    assert rows[0]["fru"] == DUMMY_FRU_PRIMARY
    assert rows[0]["serial_number"] == DUMMY_SERIAL_PRIMARY
    assert rows[0]["part_number"] == DUMMY_PART_PRIMARY
    assert rows[0]["unit_name"] == DUMMY_UNIT_NAME_PRIMARY
    assert rows[0]["unit_version"] == DUMMY_UNIT_VERSION_PRIMARY
    assert f"SN: {DUMMY_SERIAL_PRIMARY}" in rows[0]["fru_text"]
    assert f"PN: {DUMMY_PART_PRIMARY}" in rows[0]["fru_text"]
    assert rows[0]["afid"] == str(DUMMY_AFID_A)
    assert rows[0]["fault_severity"] == DUMMY_ERROR_SEVERITY
    assert rows[0]["service_action_title"] == DUMMY_SERVICE_ACTION_TITLE
    empty = [row for row in rows if row["fru"] in (DUMMY_FRU_SECONDARY, DUMMY_FRU_TERTIARY)]
    assert len(empty) == 2
    assert all(row["afid"] == "" for row in empty)
    assert list(rows[0].keys()) == list(AFID_FRU_CSV_COLUMNS)
