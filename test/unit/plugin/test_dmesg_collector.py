###############################################################################
#
# MIT License
#
# Copyright (c) 2025 Advanced Micro Devices, Inc.
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
from nodescraper.interfaces.task import SystemCompatibilityError
from nodescraper.models.systeminfo import OSFamily
from nodescraper.plugins.inband.dmesg.dmesg_collector import DmesgCollector
from nodescraper.plugins.inband.dmesg.dmesgdata import DmesgData


def test_get_new_lines():
    """Test the new lines method"""

    initial_dmesg = (
        "2023-06-01T01:00:00,685236-05:00 test message1\n"
        "2023-06-01T02:30:00,685106-05:00 test message2\n"
        "2023-06-01T03:00:00,983214-05:00 test message3\n"
        "2023-06-01T03:20:00,635178-05:00 test message4\n"
        "2023-06-01T03:25:00,635178-05:00 test message5"
    )

    new_dmesg = (
        "2023-06-01T01:00:00,685236-05:00 test message1\n"
        "2023-06-01T02:30:00,685106-05:00 test message2\n"
        "2023-06-01T03:00:00,983214-05:00 test message3\n"
        "2023-06-01T03:20:00,635178-05:00 test message4\n"
        "2023-06-01T03:25:00,635178-05:00 test message5\n"
        "2023-06-01T03:30:00,635178-05:00 test message7\n"
        "2023-06-01T03:35:00,635178-05:00 test message8\n"
        "2023-06-01T03:36:00,635178-05:00 test message9"
    )

    exp_new_lines = (
        "2023-06-01T03:30:00,635178-05:00 test message7\n"
        "2023-06-01T03:35:00,635178-05:00 test message8\n"
        "2023-06-01T03:36:00,635178-05:00 test message9"
    )

    new_lines = DmesgData.get_new_dmesg_lines(initial_dmesg, new_dmesg)

    assert new_lines == exp_new_lines


def test_dmesg_collection(system_info, conn_mock):
    system_info.os_family = OSFamily.LINUX
    collector = DmesgCollector(
        system_info=system_info,
        system_interaction_level=SystemInteractionLevel.INTERACTIVE,
        connection=conn_mock,
    )

    dmesg = (
        "2023-06-01T01:00:00,685236-05:00 test message1\n"
        "2023-06-01T02:30:00,685106-05:00 test message2\n"
        "2023-06-01T03:00:00,983214-05:00 test message3\n"
        "      kernel:[Hardware Error]: IPID: 0x0001400136430400, Syndrome: 0x0000000000001005\n"
        "      Message from syslogd@pp-128-b6-2 at Feb  8 08:25:18 ...\n"
        "   \n"
        "2023-06-01T03:20:00,635178-05:00 test message4\n"
        "2023-06-01T03:25:00,635178-05:00 test message5\n"
    )
    conn_mock.run_command.return_value = CommandArtifact(
        exit_code=0,
        stdout=dmesg,
        stderr="",
        command="dmesg --time-format iso",
    )

    res, data = collector.collect_data()
    assert res.status == ExecutionStatus.OK
    assert data is not None
    assert data.dmesg_content == dmesg


def test_bad_exit_code(conn_mock, system_info):

    conn_mock.run_command.return_value = CommandArtifact(
        exit_code=1,
        stdout="2023-06-01T01:00:00,685236-05:00 test message1\n",
        stderr="",
        command="dmesg --time-format iso",
    )

    collector = DmesgCollector(
        system_info=system_info,
        system_interaction_level=SystemInteractionLevel.INTERACTIVE,
        connection=conn_mock,
    )

    res, _ = collector.collect_data()
    assert res.status == ExecutionStatus.ERROR
    assert len(res.events) == 1
    assert res.events[0].description == "Error reading dmesg"


def test_run_dmesg_windows(conn_mock, system_info):
    system_info.os_family = OSFamily.WINDOWS
    with pytest.raises(SystemCompatibilityError, match="WINDOWS OS family is not supported"):
        DmesgCollector(
            system_info=system_info,
            system_interaction_level=SystemInteractionLevel.INTERACTIVE,
            connection=conn_mock,
        )


def test_data_model():
    dmesg_data1 = DmesgData.import_model(
        {"dmesg_content": "2023-06-01T01:00:00,685236-05:00 test message1\n"}
    )
    dmesg_data2 = DmesgData.import_model(
        {"dmesg_content": "2023-06-01T02:30:00,685106-05:00 test message2\n"}
    )

    dmesg_data2.merge_data(dmesg_data1)
    assert dmesg_data2.dmesg_content == (
        "2023-06-01T01:00:00,685236-05:00 test message1\n2023-06-01T02:30:00,685106-05:00 test message2"
    )
