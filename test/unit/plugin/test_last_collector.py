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
from errorscraper.plugins.inband.last.last_collector import LastCollector
from errorscraper.plugins.inband.last.lastdata import LastData, LastDataModel


@pytest.fixture
def collector(system_info, conn_mock):
    return LastCollector(
        system_info=system_info,
        system_interaction_level=SystemInteractionLevel.PASSIVE,
        connection=conn_mock,
    )


def test_still_logged_in(collector, conn_mock):
    # last command when user is still logged in

    collector.system_info.os_family = OSFamily.LINUX
    conn_mock.run_command.return_value = CommandArtifact(
        exit_code=0,
        stdout=(
            "user  pts/1  00.000.000.000 Tue Mar 11 10:37:20 2025   still logged in\n"
            "wtmp begins Tue Jan 28 11:41:48 2025"
        ),
        stderr="",
        command="last -Fiwd",
    )

    res, data = collector.collect_data()
    assert res.status == ExecutionStatus.OK
    assert data == LastDataModel(
        last_data=[
            LastData(
                user="user",
                terminal="pts/1",
                ip_address="00.000.000.000",
                login_time="Tue Mar 11 10:37:20 2025",
                logout_time=None,
                duration=None,
            )
        ]
    )


def test_last_shutdown(collector, conn_mock):
    # last command when system is shutdown

    collector.system_info.os_family = OSFamily.LINUX
    conn_mock.run_command.return_value = CommandArtifact(
        exit_code=0,
        stdout=(
            "shutdown  system down  0.0.0.0  Mon Feb 24 11:20:44 2025 - Mon Feb 24 11:23:59 2025  (00:03)\n"
            "wtmp begins Tue Jan 28 11:41:48 2025"
        ),
        stderr="",
        command="last -Fiwd",
    )

    res, data = collector.collect_data()
    assert res.status == ExecutionStatus.OK
    assert data == LastDataModel(
        last_data=[
            LastData(
                user="shutdown",
                terminal="system down",
                ip_address="0.0.0.0",
                login_time="Mon Feb 24 11:20:44 2025",
                logout_time="Mon Feb 24 11:23:59 2025",
                duration="00:03",
            )
        ]
    )


def test_last_data_length(collector, conn_mock):
    # test multiple outputs of last command

    collector.system_info.os_family = OSFamily.LINUX
    conn_mock.run_command.return_value = CommandArtifact(
        exit_code=0,
        stdout=(
            "shutdown  system down  0.0.0.0  Mon Feb 24 11:20:44 2025 - Mon Feb 24 11:23:59 2025  (00:03)\n"
            "user  pts/1  00.000.000.000 Tue Mar 11 10:37:20 2025   still logged in\n"
            "user  pts/2  00.000.000.000  Mon Feb 24 11:09:30 2025 - Mon Feb 24 11:20:41 2025  (00:11)\n"
            "wtmp begins Tue Jan 28 11:41:48 2025"
        ),
        stderr="",
        command="last -Fiwd",
    )

    res, data = collector.collect_data()
    assert res.status == ExecutionStatus.OK
    assert len(data.last_data) == 3
