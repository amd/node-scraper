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
import json

import pytest

from nodescraper.connection.inband.inband import CommandArtifact
from nodescraper.enums.executionstatus import ExecutionStatus
from nodescraper.enums.systeminteraction import SystemInteractionLevel
from nodescraper.plugins.inband.switch.scale_out_arista.scale_out_arista_collector import (
    ScaleOutAristaCollector,
)


@pytest.fixture
def collector(system_info, conn_mock):
    return ScaleOutAristaCollector(
        system_info=system_info,
        system_interaction_level=SystemInteractionLevel.PASSIVE,
        connection=conn_mock,
    )


def test_expand_port_name():
    assert ScaleOutAristaCollector._expand_port_name("Et1/1") == "Ethernet1/1"
    assert ScaleOutAristaCollector._expand_port_name("Ethernet1/1") == "Ethernet1/1"


def test_is_ethernet_port():
    assert ScaleOutAristaCollector._is_ethernet_port("Ethernet1/1") is True
    assert ScaleOutAristaCollector._is_ethernet_port("Port-Channel1") is False
    assert ScaleOutAristaCollector._is_ethernet_port("Management1") is False


def test_get_port_status_filters_non_ethernet(collector, conn_mock):
    payload = {
        "interfaceStatuses": {
            "Ethernet1/1": {
                "linkStatus": "connected",
                "duplex": "duplexFull",
                "lineProtocolStatus": "up",
            },
            "Port-Channel1": {"linkStatus": "connected"},
            "Management1": {"linkStatus": "connected"},
        }
    }
    conn_mock.run_command.return_value = CommandArtifact(
        exit_code=0,
        stdout=json.dumps(payload),
        stderr="",
        command="show interfaces status | json | no-more",
    )

    result = collector.get_port_status()

    assert result is not None
    assert list(result.keys()) == ["Ethernet1/1"]


def test_html_view_reruns_command_without_json(collector, conn_mock):
    from nodescraper.plugins.inband.switch.scale_out_arista.collector_args import (
        ScaleOutAristaCollectorArgs,
    )

    collector.apply_collection_html_view(ScaleOutAristaCollectorArgs(html_view=True))
    version_json = {"mfgName": "Arista Networks", "version": "4.28.0F"}
    pretty_stdout = "Arista DCS-7050CX3-32S-C32\nHardware version: 11.00"
    conn_mock.run_command.side_effect = [
        CommandArtifact(
            exit_code=0,
            stdout=json.dumps(version_json),
            stderr="",
            command="show version | json | no-more",
        ),
        CommandArtifact(
            exit_code=0,
            stdout=pretty_stdout,
            stderr="",
            command="show version | no-more",
        ),
    ]

    collector.get_version()

    assert conn_mock.run_command.call_count == 2
    second_call = conn_mock.run_command.call_args_list[1]
    second_command = second_call.args[0] if second_call.args else second_call.kwargs["command"]
    assert second_command == "show version | no-more"
    commands = [artifact.command for artifact in collector.result.artifacts]
    assert "show version | json | no-more" in commands
    assert "show version | no-more" in commands
    pretty_artifact = next(
        artifact
        for artifact in collector.result.artifacts
        if artifact.command == "show version | no-more"
    )
    assert pretty_artifact.stdout == pretty_stdout
    assert pretty_artifact.log_html is True
    json_artifact = next(
        artifact
        for artifact in collector.result.artifacts
        if artifact.command == "show version | json | no-more"
    )
    assert json_artifact.log_html is False


def test_preflight_not_ran_when_not_arista(collector, conn_mock):
    conn_mock.run_command.return_value = CommandArtifact(
        exit_code=0,
        stdout=json.dumps({"mfgName": "Cisco Systems", "version": "1.0"}),
        stderr="",
        command="show version | json | no-more",
    )

    version = collector._preflight_check()

    assert version is None
    assert collector.result.status == ExecutionStatus.NOT_RAN
