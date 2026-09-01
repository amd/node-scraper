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
import logging

from serviceability_dummy_data import DUMMY_AFID_A, DUMMY_UNIT_A

from nodescraper.enums import ExecutionStatus
from nodescraper.models import DataPluginResult, PluginResult, TaskResult
from nodescraper.plugins.serviceability.se_models import (
    HubTriageResult,
    ServiceabilityBlock,
)
from nodescraper.plugins.serviceability.serviceability_data import (
    ServiceabilityDataModel,
)
from nodescraper.resultcollators.tablesummary import TableSummary


def test_tablesummary_prints_connection_serviceability_then_plugin(caplog):
    block = ServiceabilityBlock(
        hub_top_results=[
            HubTriageResult(
                afid=DUMMY_AFID_A,
                location=DUMMY_UNIT_A,
                service_action_num=11018,
                service_action_title="Check and Retry FW Bundle",
                priority=1,
                sa_severity=20,
                tier_label="Secondary",
                hub_sort_priority=1000,
            )
        ],
        hub_triage_results=[
            HubTriageResult(
                afid=DUMMY_AFID_A,
                location=DUMMY_UNIT_A,
                service_action_num=11018,
                service_action_title="Check and Retry FW Bundle",
                priority=1,
                sa_severity=20,
                tier_label="Secondary",
                hub_sort_priority=1000,
            )
        ],
    )
    plugin_results = [
        PluginResult(
            status=ExecutionStatus.OK,
            source="Mi4xxServiceabilityPlugin",
            message="Plugin tasks completed successfully",
            result_data=DataPluginResult(
                system_data=ServiceabilityDataModel(serviceability=block),
            ),
        )
    ]
    connection_results = [
        TaskResult(
            task="RedfishConnectionManager",
            status=ExecutionStatus.OK,
            message="task completed successfully",
        )
    ]

    logger = logging.getLogger("test_tablesummary")
    caplog.set_level(logging.INFO, logger="test_tablesummary")
    TableSummary(logger=logger).collate_results(plugin_results, connection_results)

    output = caplog.text
    connection_pos = output.index("| Connection")
    serviceability_pos = output.index("Top Hub service action")
    plugin_pos = output.index("| Plugin")
    assert connection_pos < serviceability_pos < plugin_pos
