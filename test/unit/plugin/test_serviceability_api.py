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
from serviceability_dummy_data import DUMMY_AFID_A, DUMMY_UNIT_A

from nodescraper.plugins.serviceability.se_models import (
    AfidEvent,
    HubTriageResult,
    ServiceabilityBlock,
)
from nodescraper.plugins.serviceability.serviceability_api import (
    export_serviceability_json,
)


def test_export_serviceability_json_keeps_raw_hub_and_drops_duplicate_rows():
    block = ServiceabilityBlock(
        afid_events=[
            AfidEvent(
                afid=DUMMY_AFID_A, serviceable_unit="Instinct_EAM_0", time="2025-01-01T00:00:00Z"
            )
        ],
        hub_analyze_response={
            "schema_version": "1.0",
            "status": "ok",
            "triage": {
                "top": [{"afid": DUMMY_AFID_A, "location": DUMMY_UNIT_A, "se_sort_priority": 1000}],
                "results": [
                    {"afid": DUMMY_AFID_A, "location": DUMMY_UNIT_A, "se_sort_priority": 1000}
                ],
                "multi_afid_summary": [],
            },
            "pid": "SAG-00000",
            "revision": "1.0.0",
        },
        hub_top_results=[
            HubTriageResult(
                afid=DUMMY_AFID_A,
                location=DUMMY_UNIT_A,
                service_action_num=199,
                hub_sort_priority=1000,
            )
        ],
        hub_triage_results=[
            HubTriageResult(
                afid=DUMMY_AFID_A,
                location=DUMMY_UNIT_A,
                service_action_num=199,
                hub_sort_priority=1000,
            )
        ],
    )

    payload = export_serviceability_json(block)

    assert payload["hub_analyze_response"]["triage"]["top"][0]["se_sort_priority"] == 1000
    assert "hub_top_results" not in payload
    assert "hub_triage_results" not in payload
