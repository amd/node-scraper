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
from unittest.mock import patch

import pytest

from nodescraper.connection.redfish import (
    RedfishGetResult,
    RedfishSshProxyConnectionManager,
)
from nodescraper.enums import ExecutionStatus
from nodescraper.pluginregistry import PluginRegistry
from nodescraper.plugins.ooband.amc_redfish_diag import (
    AmcDiagCollectionSpec,
    AmcRedfishDiagCollector,
    AmcRedfishDiagCollectorArgs,
    AmcRedfishDiagPlugin,
)


@pytest.fixture
def amc_collector(system_info, redfish_conn_mock):
    redfish_conn_mock.api_root = "redfish/v1"
    return AmcRedfishDiagCollector(
        system_info=system_info,
        connection=redfish_conn_mock,
    )


def test_amc_redfish_diag_plugin_registers():
    assert AmcRedfishDiagPlugin.is_valid()
    assert AmcRedfishDiagPlugin.CONNECTION_TYPE is RedfishSshProxyConnectionManager
    assert "AmcRedfishDiagPlugin" in PluginRegistry().plugins
    assert "RedfishSshProxyConnectionManager" in PluginRegistry().connection_managers


def test_amc_collector_no_jobs(amc_collector):
    result, data = amc_collector.collect_data(args=AmcRedfishDiagCollectorArgs(collections=[]))
    assert result.status == ExecutionStatus.NOT_RAN
    assert data is None


def _get_side_effect(path):
    p = str(path)
    if p.endswith("/LogServices"):
        if "Managers" in p:
            oid = "/redfish/v1/Managers/dummy-amc/LogServices/Dump"
        else:
            oid = "/redfish/v1/Systems/dummy-system/LogServices/DiagLogs"
        return RedfishGetResult(
            path=p,
            success=True,
            data={"Members": [{"@odata.id": oid}]},
            status_code=200,
        )
    if p.endswith("/Dump") or p.endswith("/DiagLogs"):
        return RedfishGetResult(
            path=p,
            success=True,
            data={"Actions": {"#LogService.CollectDiagnosticData": {}}},
            status_code=200,
        )
    return RedfishGetResult(path=p, success=False, error="unexpected", status_code=404)


@patch("nodescraper.plugins.ooband.amc_redfish_diag.amc_diag_collector.collect_oem_diagnostic_data")
def test_amc_collector_runs_manager_and_system_jobs(mock_collect, amc_collector):
    mock_collect.return_value = (b"archive", {"Id": "1"}, None)
    amc_collector.connection.run_get.side_effect = _get_side_effect
    result, data = amc_collector.collect_data(
        args=AmcRedfishDiagCollectorArgs(
            manager_ids=["dummy-amc"],
            system_ids=["dummy-system"],
            collections=[
                AmcDiagCollectionSpec(root="Managers", diagnostic_data_type="Manager"),
                AmcDiagCollectionSpec(
                    root="Systems",
                    diagnostic_data_type="OEM",
                    oem_data_type="AllLogs",
                ),
            ],
        )
    )
    assert result.status == ExecutionStatus.OK
    assert data is not None
    assert "Managers:Manager" in data.results
    assert "Systems:OEM:AllLogs" in data.results
    assert mock_collect.call_count == 2
    first_kwargs = mock_collect.call_args_list[0].kwargs
    assert first_kwargs["diagnostic_data_type"] == "Manager"
    second_kwargs = mock_collect.call_args_list[1].kwargs
    assert second_kwargs["diagnostic_data_type"] == "OEM"
    assert second_kwargs["oem_diagnostic_type"] == "AllLogs"


@patch("nodescraper.plugins.ooband.amc_redfish_diag.amc_diag_collector.collect_oem_diagnostic_data")
def test_amc_collector_missing_log_service(mock_collect, amc_collector):
    amc_collector.connection.run_get.return_value = RedfishGetResult(
        path="/redfish/v1/Managers/dummy-amc/LogServices",
        success=True,
        data={"Members": []},
        status_code=200,
    )
    result, data = amc_collector.collect_data(
        args=AmcRedfishDiagCollectorArgs(
            manager_ids=["dummy-amc"],
            system_ids=["dummy-system"],
            collections=[
                AmcDiagCollectionSpec(root="Managers", diagnostic_data_type="Manager"),
            ],
        )
    )
    assert result.status == ExecutionStatus.ERROR
    assert data is not None
    assert data.results["Managers:Manager"].success is False
    mock_collect.assert_not_called()
