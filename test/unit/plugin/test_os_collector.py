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
from nodescraper.models.systeminfo import OSFamily
from nodescraper.plugins.inband.os.os_collector import OsCollector
from nodescraper.plugins.inband.os.osdata import OsDataModel


@pytest.fixture
def collector(system_info, conn_mock):
    return OsCollector(
        system_info=system_info,
        system_interaction_level=SystemInteractionLevel.PASSIVE,
        connection=conn_mock,
    )


@pytest.mark.parametrize(
    "stdout, version_stdout, expected_os, expected_version",
    [
        ("Ubuntu 22.04.4 LTS", 'VERSION_ID="22.04"', "Ubuntu 22.04.4 LTS", "22.04"),
        (
            'PRETTY_NAME="Oracle Linux Server 8.8"',
            'VERSION_ID="8.8"',
            "Oracle Linux Server 8.8",
            "8.8",
        ),
        ('PRETTY_NAME="CentOS Linux 8"', 'VERSION_ID="8"', "CentOS Linux 8", "8"),
        (
            'PRETTY_NAME="Rocky Linux 9.3 (Blue Onyx)"',
            'VERSION_ID="9.3"',
            "Rocky Linux 9.3 (Blue Onyx)",
            "9.3",
        ),
        ('PRETTY_NAME="openSUSE Leap 15.6"', 'VERSION_ID="15.6"', "openSUSE Leap 15.6", "15.6"),
        ("Ubuntu 22.04.5 LTS", 'VERSION_ID="22.04"', "Ubuntu 22.04.5 LTS", "22.04"),
        (
            'PRETTY_NAME="Fedora Linux 41 (Container Image)"',
            "VERSION_ID=41",
            "Fedora Linux 41 (Container Image)",
            "41",
        ),
        (
            'PRETTY_NAME="Arch Linux"',
            "VERSION_ID=20241124.0.282387",
            "Arch Linux",
            "20241124.0.282387",
        ),
        (
            'PRETTY_NAME="Debian GNU/Linux 12 (bookworm)"',
            'VERSION_ID="12"',
            "Debian GNU/Linux 12 (bookworm)",
            "12",
        ),
    ],
)
def test_os_collector_linux(
    collector, conn_mock, stdout, version_stdout, expected_os, expected_version
):
    conn_mock.run_command.side_effect = [
        CommandArtifact(exit_code=0, stdout=stdout, stderr="", command="cmd1"),
        CommandArtifact(exit_code=0, stdout=version_stdout, stderr="", command="cmd2"),
    ]

    result, data = collector.collect_data()
    assert result.status == ExecutionStatus.OK
    assert data == OsDataModel(os_name=expected_os, os_version=expected_version)


def test_os_collector_windows(system_info, conn_mock):
    system_info.os_family = OSFamily.WINDOWS
    collector_inst = OsCollector(
        system_info=system_info,
        system_interaction_level=SystemInteractionLevel.PASSIVE,
        connection=conn_mock,
    )

    conn_mock.run_command.side_effect = [
        CommandArtifact(
            exit_code=0,
            stdout=r"\n\n\nCaption=Microsoft Windows 11 Enterprise",
            stderr="",
            command="wmic1",
        ),
        CommandArtifact(
            exit_code=0, stdout=r"\n\n\nVersion=10.0.22621\n\n\n", stderr="", command="wmic2"
        ),
    ]

    _, data = collector_inst.collect_data()
    assert collector_inst.result.status == ExecutionStatus.OK
    assert data == OsDataModel(os_name="Microsoft Windows 11 Enterprise", os_version="10.0.22621")


def test_os_collector_error(collector, conn_mock, system_info):
    system_info.os_family = OSFamily.LINUX
    conn_mock.run_command.side_effect = [
        CommandArtifact(exit_code=1, stdout="Ubuntu 22.04.4 LTS", stderr="", command="cmd1"),
        CommandArtifact(exit_code=1, stdout="Ubuntu 22.04.4 LTS", stderr="", command="cmd2"),
    ]

    _, data = collector.collect_data()
    assert data is None
