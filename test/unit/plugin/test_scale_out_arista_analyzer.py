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
import pytest

from nodescraper.enums.executionstatus import ExecutionStatus
from nodescraper.plugins.inband.switch.scale_out_arista.analyzer_args import (
    ScaleOutAristaAnalyzerArgs,
)
from nodescraper.plugins.inband.switch.scale_out_arista.scale_out_arista_analyzer import (
    ScaleOutAristaAnalyzer,
)
from nodescraper.plugins.inband.switch.scale_out_arista.scaleoutaristadata import (
    AristaPortStatus,
    AristaSystemEnv,
    FanConfiguration,
    PortData,
    ScaleOutAristaDataModel,
    VlanInformation,
)


@pytest.fixture
def analyzer(system_info):
    return ScaleOutAristaAnalyzer(system_info=system_info)


def _port(bandwidth=400000000000, link_status="connected"):
    return PortData(
        port_status=AristaPortStatus(
            link_status=link_status,
            duplex="duplexFull",
            line_protocol_status="up",
            bandwidth=bandwidth,
            vlan_information=VlanInformation(
                interface_mode="routed",
                interface_forwarding_model="routed",
            ),
        )
    )


def test_expected_port_bandwidth_error(analyzer):
    data = ScaleOutAristaDataModel(port={"Ethernet1/1": _port(bandwidth=100000000000)})
    result = analyzer.analyze_data(
        data, ScaleOutAristaAnalyzerArgs(expected_port_bandwidth=400000000000)
    )
    assert result.status == ExecutionStatus.ERROR
    assert "errors" in result.message.lower()


def test_analysis_ports_filter(analyzer):
    data = ScaleOutAristaDataModel(
        port={
            "Ethernet1/1": _port(),
            "Ethernet1/2": _port(link_status="notconnect"),
        }
    )
    result = analyzer.analyze_data(data, ScaleOutAristaAnalyzerArgs(analysis_ports=["1/1"]))
    assert all("Ethernet1/2" not in event.description for event in result.events)


def test_system_env_fan_error(analyzer):
    data = ScaleOutAristaDataModel(
        system_env=AristaSystemEnv(
            system_status="coolingOk",
            fans_status="fanAlarmOk",
            fan_tray_slots=[FanConfiguration(label="Fan1", status="failed")],
        )
    )
    result = analyzer.analyze_data(data)
    assert result.status == ExecutionStatus.ERROR
    assert result.message.startswith("Arista errors and warnings detected")


def test_healthy_port_has_no_errors(analyzer):
    data = ScaleOutAristaDataModel(port={"Ethernet1/1": _port()})
    result = analyzer.analyze_data(data)
    assert result.status != ExecutionStatus.ERROR
    assert "errors detected" not in result.message.lower()
