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
from nodescraper.plugins.inband.switch.scale_out_arista.scale_out_arista_analyzer import (
    ScaleOutAristaAnalyzer,
)
from nodescraper.plugins.inband.switch.scale_out_arista.scaleoutaristadata import (
    AristaPortStatus,
    PortData,
    ScaleOutAristaDataModel,
    VlanInformation,
)
from nodescraper.plugins.inband.switch.scale_out_dell.scale_out_dell_analyzer import (
    ScaleOutDellAnalyzer,
)
from nodescraper.plugins.inband.switch.scale_out_dell.scaleoutdelldata import (
    DellInterfaceCounters,
    DellInterfaceStatus,
    DellPortData,
    ScaleOutDellDataModel,
)


@pytest.fixture
def analyzer(system_info):
    return ScaleOutAristaAnalyzer(system_info=system_info)


def test_nested_vlan_information_error(analyzer):
    data = ScaleOutAristaDataModel(
        port={
            "Ethernet1/1": PortData(
                port_status=AristaPortStatus(
                    link_status="connected",
                    duplex="duplexFull",
                    line_protocol_status="up",
                    vlan_information=VlanInformation(
                        interface_mode="trunk",
                        interface_forwarding_model="routed",
                    ),
                )
            )
        }
    )

    result = analyzer.analyze_data(data)

    assert result.status == ExecutionStatus.ERROR
    assert any("interface_mode" in event.description for event in result.events)


def test_nested_vlan_information_ok(analyzer):
    data = ScaleOutAristaDataModel(
        port={
            "Ethernet1/1": PortData(
                port_status=AristaPortStatus(
                    link_status="connected",
                    duplex="duplexFull",
                    line_protocol_status="up",
                    vlan_information=VlanInformation(
                        interface_mode="routed",
                        interface_forwarding_model="routed",
                    ),
                )
            )
        }
    )

    result = analyzer.analyze_data(data)

    assert result.status != ExecutionStatus.ERROR
    assert not any("interface_mode" in event.description for event in result.events)


def test_missing_nested_vlan_information_warns(analyzer):
    data = ScaleOutAristaDataModel(
        port={
            "Ethernet1/1": PortData(
                port_status=AristaPortStatus(
                    link_status="connected",
                    duplex="duplexFull",
                    line_protocol_status="up",
                    vlan_information=None,
                )
            )
        }
    )

    result = analyzer.analyze_data(data)

    assert result.status == ExecutionStatus.WARNING
    assert any("vlan_information" in event.description for event in result.events)


@pytest.fixture
def dell_analyzer(system_info):
    return ScaleOutDellAnalyzer(system_info=system_info)


def test_dell_analysis_ports_accepts_eth_prefix(dell_analyzer):
    data = ScaleOutDellDataModel(
        port={
            "Eth1/1/1": DellPortData(
                interface_status=DellInterfaceStatus(oper="up", speed=400000),
                interface_counters=DellInterfaceCounters(
                    state="U",
                    rx_err=0,
                    rx_oversize=0,
                    tx_err=0,
                    tx_oversize=0,
                    rx_drp=0,
                    tx_drp=0,
                ),
            ),
            "Eth1/1/2": DellPortData(
                interface_status=DellInterfaceStatus(oper="down", speed=400000),
            ),
        }
    )
    from nodescraper.plugins.inband.switch.scale_out_dell.analyzer_args import (
        ScaleOutDellAnalyzerArgs,
    )

    result = dell_analyzer.analyze_data(data, ScaleOutDellAnalyzerArgs(analysis_ports=["1/1/1"]))
    assert all("Eth1/1/2" not in event.description for event in result.events)


def test_analyzer_messages_distinguish_errors_and_warnings(analyzer):
    data = ScaleOutAristaDataModel(
        port={
            "Ethernet1/1": PortData(
                port_status=AristaPortStatus(
                    link_status="notconnect",
                    duplex="duplexFull",
                    line_protocol_status="up",
                    vlan_information=VlanInformation(
                        interface_mode="routed",
                        interface_forwarding_model="routed",
                    ),
                )
            )
        }
    )
    result = analyzer.analyze_data(data)
    assert result.status == ExecutionStatus.ERROR
    assert result.message.startswith("Arista errors and warnings detected")
