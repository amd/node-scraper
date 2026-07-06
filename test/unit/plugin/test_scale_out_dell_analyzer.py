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
from nodescraper.plugins.inband.switch.scale_out_dell.analyzer_args import (
    ScaleOutDellAnalyzerArgs,
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
    return ScaleOutDellAnalyzer(system_info=system_info)


def _port(oper="up", speed=400000, rx_drp=0):
    return DellPortData(
        interface_status=DellInterfaceStatus(oper=oper, speed=speed),
        interface_counters=DellInterfaceCounters(
            state="U",
            rx_err=0,
            rx_oversize=0,
            tx_err=0,
            tx_oversize=0,
            rx_drp=rx_drp,
            tx_drp=0,
        ),
    )


def test_expected_port_speed_error(analyzer):
    data = ScaleOutDellDataModel(port={"Eth1/1": _port(speed=100000)})
    result = analyzer.analyze_data(data, ScaleOutDellAnalyzerArgs(expected_port_speed=400000))
    assert result.status == ExecutionStatus.ERROR
    assert "errors" in result.message.lower()


def test_expected_port_speed_custom_passes(analyzer):
    data = ScaleOutDellDataModel(port={"Eth1/1": _port(speed=100000)})
    result = analyzer.analyze_data(data, ScaleOutDellAnalyzerArgs(expected_port_speed=100000))
    assert result.status != ExecutionStatus.ERROR
    assert "errors detected" not in result.message.lower()


def test_analysis_ports_filter(analyzer):
    data = ScaleOutDellDataModel(
        port={
            "Eth1/1": _port(),
            "Eth1/2": _port(oper="down"),
        }
    )
    result = analyzer.analyze_data(data, ScaleOutDellAnalyzerArgs(analysis_ports=["1/1"]))
    assert "Eth1/2" not in " ".join(event.description for event in result.events)


def test_warnings_only_message(analyzer):
    data = ScaleOutDellDataModel(port={"Eth1/1": _port(rx_drp=5)})
    result = analyzer.analyze_data(data)
    assert result.status == ExecutionStatus.WARNING
    assert result.message.startswith("Dell warnings detected")


def test_invalid_analysis_ports(analyzer):
    data = ScaleOutDellDataModel(port={"Eth1/1": _port()})
    result = analyzer.analyze_data(data, ScaleOutDellAnalyzerArgs(analysis_ports=["bad port"]))
    assert result.status == ExecutionStatus.EXECUTION_FAILURE
