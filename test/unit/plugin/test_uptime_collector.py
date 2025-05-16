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

from errorscraper.connection.inband.inband import CommandArtifact
from errorscraper.enums.executionstatus import ExecutionStatus
from errorscraper.enums.systeminteraction import SystemInteractionLevel
from errorscraper.models.systeminfo import OSFamily
from errorscraper.plugins.inband.uptime.uptime_collector import UptimeCollector
from errorscraper.plugins.inband.uptime.uptimedata import UptimeDataModel


@pytest.fixture
def collector(system_info, conn_mock):
    return UptimeCollector(
        system_info=system_info,
        system_interaction_level=SystemInteractionLevel.PASSIVE,
        connection=conn_mock,
    )


def test_uptime_short(collector, conn_mock):
    # Simulate uptime < 24 hours
    collector.system_info.os_family = OSFamily.LINUX
    conn_mock.run_command.return_value = CommandArtifact(
        exit_code=0,
        stdout="15:10:16 up  2:31,  1 user,  load average: 0.24, 0.18, 0.12",
        stderr="",
        command="uptime",
    )

    res, data = collector.collect_data()
    assert res.status == ExecutionStatus.OK
    assert data == UptimeDataModel(current_time="15:10:16", uptime="2:31")


def test_uptime_long(collector, conn_mock):
    # Simulate uptime > 24 hours
    collector.system_info.os_family = OSFamily.LINUX
    conn_mock.run_command.return_value = CommandArtifact(
        exit_code=0,
        stdout="12:49:10 up 25 days, 21:30, 28 users,  load average: 0.50, 0.66, 0.52",
        stderr="",
        command="uptime",
    )

    res, data = collector.collect_data()
    assert res.status == ExecutionStatus.OK
    assert data == UptimeDataModel(current_time="12:49:10", uptime="25 days, 21:30")
