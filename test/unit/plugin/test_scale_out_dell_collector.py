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

from nodescraper.connection.inband.inband import CommandArtifact
from nodescraper.enums.executionstatus import ExecutionStatus
from nodescraper.enums.systeminteraction import SystemInteractionLevel
from nodescraper.plugins.inband.switch.scale_out_dell.scale_out_dell_collector import (
    ScaleOutDellCollector,
)


@pytest.fixture
def collector(system_info, conn_mock):
    return ScaleOutDellCollector(
        system_info=system_info,
        system_interaction_level=SystemInteractionLevel.PASSIVE,
        connection=conn_mock,
    )


SAMPLE_INTERFACE_STATUS = """\
Interface      Description                         Oper    Reason      AutoNeg  Speed     MTU      Alternate Name
Eth1/1         server-prod-a                       up      none        on       400000    9100     -
Eth1/2         connection to  leaf  with  spaces   up      none        on       400000    9100     Eth1/2
Eth1/3         backup uplink active                down    admin       off      100000    1500     N/A
Eth1/4         line marked up in description       up      none        on       400000    9100     -
"""


def test_parse_interface_status_line_simple():
    parsed = ScaleOutDellCollector._parse_interface_status_line(
        "Eth1/1         server-prod-a                       up      none        on       400000    9100     -"
    )
    assert parsed == {
        "name": "Eth1/1",
        "description": "server-prod-a",
        "oper": "up",
        "reason": "none",
        "auto_neg": "on",
        "speed": 400000,
        "mtu": 9100,
        "alternate_name": "-",
    }


def test_parse_interface_status_line_description_with_extra_spaces():
    parsed = ScaleOutDellCollector._parse_interface_status_line(
        "Eth1/2         connection to  leaf  with  spaces   up      none        on       400000    9100     Eth1/2"
    )
    assert parsed is not None
    assert parsed["description"] == "connection to  leaf  with  spaces"
    assert parsed["oper"] == "up"
    assert parsed["speed"] == 400000
    assert parsed["alternate_name"] == "Eth1/2"


def test_parse_interface_status_line_description_contains_up_token():
    parsed = ScaleOutDellCollector._parse_interface_status_line(
        "Eth1/4         line marked up in description       up      none        on       400000    9100     -"
    )
    assert parsed is not None
    assert parsed["description"] == "line marked up in description"
    assert parsed["oper"] == "up"
    assert parsed["speed"] == 400000


def test_parse_interface_status_line_down():
    parsed = ScaleOutDellCollector._parse_interface_status_line(
        "Eth1/3         backup uplink active                down    admin       off      100000    1500     N/A"
    )
    assert parsed is not None
    assert parsed["oper"] == "down"
    assert parsed["reason"] == "admin"
    assert parsed["speed"] == 100000
    assert parsed["mtu"] == 1500


def test_parse_interface_status_line_skips_header():
    assert (
        ScaleOutDellCollector._parse_interface_status_line(
            "Interface      Description                         Oper    Reason      AutoNeg  Speed     MTU      Alternate Name"
        )
        is None
    )


def test_canonical_eth_port_rejects_invalid_name():
    assert ScaleOutDellCollector._canonical_eth_port('Eth1"; evil') is None


def test_get_detail_counters_skips_invalid_port(collector, conn_mock):
    conn_mock.run_command.return_value = CommandArtifact(
        exit_code=0,
        stdout="",
        stderr="",
        command='sonic-cli -c "show interface counters Eth1/1 | no-more"',
    )

    result = collector.get_detail_counters(["Eth1/1", 'Eth1"; evil'])

    assert conn_mock.run_command.call_count == 1
    assert result is None or "Eth1/1" in result


def test_preflight_not_ran_when_not_dell(collector, conn_mock):
    conn_mock.run_command.return_value = CommandArtifact(
        exit_code=0,
        stdout="Cisco NX-OS Software",
        stderr="",
        command='sonic-cli -c "show version | no-more"',
    )

    assert collector._preflight_check() is False
    assert collector.result.status == ExecutionStatus.NOT_RAN


def test_get_interface_status_parses_sample_block(collector, conn_mock):
    conn_mock.run_command.return_value = CommandArtifact(
        exit_code=0,
        stdout=SAMPLE_INTERFACE_STATUS,
        stderr="",
        command='sonic-cli -c "show interface status | no-more"',
    )

    result = collector.get_interface_status()

    assert result is not None
    assert set(result.keys()) == {"Eth1/1", "Eth1/2", "Eth1/3", "Eth1/4"}
    assert result["Eth1/2"].description == "connection to  leaf  with  spaces"
    assert result["Eth1/4"].oper == "up"
    assert result["Eth1/3"].speed == 100000
