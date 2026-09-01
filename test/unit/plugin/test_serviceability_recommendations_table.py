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
from serviceability_dummy_data import (
    DUMMY_AFID_A,
    DUMMY_AFID_B,
    DUMMY_SERVICE_ACTION_NUM,
    DUMMY_TIER_CRITICAL,
    DUMMY_TIER_LABEL,
    DUMMY_UNIT_A,
    DUMMY_UNIT_B,
)

from nodescraper.enums import ExecutionStatus
from nodescraper.models import DataPluginResult, PluginResult
from nodescraper.plugins.serviceability.se_models import (
    HubTriageResult,
    ServiceabilityBlock,
)
from nodescraper.plugins.serviceability.serviceability_api import (
    build_top_service_actions,
    split_recommendation_actions,
)
from nodescraper.plugins.serviceability.serviceability_data import (
    ServiceabilityDataModel,
)
from nodescraper.plugins.serviceability.serviceability_recommendations_table import (
    emit_serviceability_recommendation_tables,
    render_serviceability_recommendation_tables,
    render_serviceability_recommendation_tables_for_plugin_results,
)


def _row(
    *,
    afid: int,
    location: str,
    sort_priority: int,
    priority: int,
    title: str,
) -> HubTriageResult:
    return HubTriageResult(
        afid=afid,
        location=location,
        service_action_num=DUMMY_SERVICE_ACTION_NUM,
        service_action_title=title,
        priority=priority,
        sa_severity=20,
        tier_label=DUMMY_TIER_CRITICAL if priority == 1 else DUMMY_TIER_LABEL,
        hub_sort_priority=sort_priority,
    )


def test_split_recommendation_rows_uses_hub_top():
    block = ServiceabilityBlock(
        hub_top_results=[
            _row(
                afid=DUMMY_AFID_A,
                location=DUMMY_UNIT_A,
                sort_priority=1000,
                priority=1,
                title="Contact Support",
            )
        ],
        hub_triage_results=[
            _row(
                afid=DUMMY_AFID_A,
                location=DUMMY_UNIT_A,
                sort_priority=1000,
                priority=1,
                title="Contact Support",
            ),
            _row(
                afid=DUMMY_AFID_B,
                location=DUMMY_UNIT_B,
                sort_priority=2000,
                priority=20,
                title="Update FW",
            ),
        ],
    )

    top, additional = split_recommendation_actions(block)

    assert len(top) == 1
    assert top[0].afid == DUMMY_AFID_A
    assert len(additional) == 1
    assert additional[0].afid == DUMMY_AFID_B


def test_render_serviceability_recommendation_tables_splits_sections():
    block = ServiceabilityBlock(
        hub_top_results=[
            _row(
                afid=DUMMY_AFID_A,
                location=DUMMY_UNIT_A,
                sort_priority=1000,
                priority=1,
                title="Contact Support",
            )
        ],
        hub_triage_results=[
            _row(
                afid=DUMMY_AFID_A,
                location=DUMMY_UNIT_A,
                sort_priority=1000,
                priority=1,
                title="Contact Support",
            ),
            _row(
                afid=DUMMY_AFID_B,
                location=DUMMY_UNIT_B,
                sort_priority=2000,
                priority=20,
                title="Update FW",
            ),
        ],
    )

    output = render_serviceability_recommendation_tables(block)

    assert "Top Hub service action (rank 1)" in output
    assert "Additional Hub service actions (rank 2)" in output
    assert f"{DUMMY_AFID_A}: Contact Support" in output
    assert f"{DUMMY_AFID_B}: Update FW" in output
    assert output.index("Top Hub service action") < output.index("Additional Hub service actions")


def test_build_top_service_actions_includes_tied_entries():
    block = ServiceabilityBlock(
        hub_top_results=[
            _row(
                afid=DUMMY_AFID_A,
                location=DUMMY_UNIT_A,
                sort_priority=1000,
                priority=1,
                title="Replace Unit",
            ),
            _row(
                afid=DUMMY_AFID_B,
                location=DUMMY_UNIT_B,
                sort_priority=1000,
                priority=1,
                title="Replace Unit",
            ),
        ],
        hub_triage_results=[
            _row(
                afid=DUMMY_AFID_A,
                location=DUMMY_UNIT_A,
                sort_priority=1000,
                priority=1,
                title="Replace Unit",
            ),
            _row(
                afid=DUMMY_AFID_B,
                location=DUMMY_UNIT_B,
                sort_priority=1000,
                priority=1,
                title="Replace Unit",
            ),
        ],
    )

    top = build_top_service_actions(block)

    assert len(top) == 2
    assert {action.afid for action in top} == {DUMMY_AFID_A, DUMMY_AFID_B}


def test_render_serviceability_recommendation_tables_for_plugin_results():
    block = ServiceabilityBlock(
        hub_top_results=[
            _row(
                afid=DUMMY_AFID_A,
                location=DUMMY_UNIT_A,
                sort_priority=1000,
                priority=1,
                title="Contact Support",
            )
        ],
        hub_triage_results=[
            _row(
                afid=DUMMY_AFID_A,
                location=DUMMY_UNIT_A,
                sort_priority=1000,
                priority=1,
                title="Contact Support",
            ),
        ],
    )
    plugin_results = [
        PluginResult(
            status=ExecutionStatus.OK,
            source="Mi4xxServiceabilityPlugin",
            message="ok",
            result_data=DataPluginResult(
                system_data=ServiceabilityDataModel(serviceability=block),
            ),
        )
    ]

    output = render_serviceability_recommendation_tables_for_plugin_results(plugin_results)

    assert "Top Hub service action" in output
    assert "Contact Support" in output


def test_emit_serviceability_recommendation_tables_writes_stdout(capsys):
    block = ServiceabilityBlock(
        hub_top_results=[
            _row(
                afid=DUMMY_AFID_A,
                location=DUMMY_UNIT_A,
                sort_priority=1000,
                priority=1,
                title="Contact Support",
            )
        ],
        hub_triage_results=[
            _row(
                afid=DUMMY_AFID_A,
                location=DUMMY_UNIT_A,
                sort_priority=1000,
                priority=1,
                title="Contact Support",
            ),
        ],
    )

    emit_serviceability_recommendation_tables(block)
    captured = capsys.readouterr()

    assert "Top Hub service action" in captured.out
    assert "Rank" in captured.out
    assert "Contact Support" in captured.out
