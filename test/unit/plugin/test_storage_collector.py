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
from nodescraper.enums.eventcategory import EventCategory
from nodescraper.enums.executionstatus import ExecutionStatus
from nodescraper.enums.systeminteraction import SystemInteractionLevel
from nodescraper.models.systeminfo import OSFamily
from nodescraper.plugins.inband.storage.storage_collector import StorageCollector
from nodescraper.plugins.inband.storage.storagedata import (
    DeviceStorageData,
    StorageDataModel,
)


@pytest.fixture
def collector(system_info, conn_mock):
    return StorageCollector(
        system_info=system_info,
        system_interaction_level=SystemInteractionLevel.PASSIVE,
        connection=conn_mock,
    )


def test_run_linux(collector, conn_mock):
    collector.system_info.os_family = OSFamily.LINUX
    conn_mock.run_command.return_value = CommandArtifact(
        exit_code=0,
        stdout=(
            "Filesystem        1B-blocks        Used    Available Use% Mounted on\n"
            "tmpfs           53929857024   103428096  53826428928   1% /run\n"
            "/dev/nvme0n1p2 943441641472 25645850624 869796294656   3% /\n"
            "tmpfs          269649281024       20480 269649260544   1% /dev/shm\n"
            "tmpfs               5242880           0      5242880   0% /run/lock\n"
            "tmpfs           53929852928        4096  53929848832   1% /run/user/8199"
        ),
        stderr="",
        command="sh -c 'df -lH | grep -v 'boot''",
    )

    result, data = collector.collect_data()
    assert result.status == ExecutionStatus.OK
    assert data == StorageDataModel(
        storage_data={
            "/dev/nvme0n1p2": DeviceStorageData(
                total=943441641472,
                free=869796294656,
                used=25645850624,
                percent=3,
            )
        }
    )


def test_run_windows(system_info, conn_mock):
    system_info.os_family = OSFamily.WINDOWS
    collector = StorageCollector(
        system_info=system_info,
        system_interaction_level=SystemInteractionLevel.PASSIVE,
        connection=conn_mock,
    )

    conn_mock.run_command.return_value = CommandArtifact(
        exit_code=0,
        stdout=("DeviceID  FreeSpace     Size\n" "C:        466435543040  1013310287872"),
        stderr="",
        command='wmic LogicalDisk Where DriveType="3" Get DeviceId,Size,FreeSpace',
    )

    result, data = collector.collect_data()
    assert result.status == ExecutionStatus.OK
    assert data == StorageDataModel(
        storage_data={
            "C:": DeviceStorageData(
                total=1013310287872,
                free=466435543040,
                used=546874744832,
                percent=53.97,
            )
        }
    )


def test_errors(collector, conn_mock):
    collector.system_info.os_family = OSFamily.LINUX
    conn_mock.run_command.return_value = CommandArtifact(
        exit_code=1,
        stdout="/dev/nvme0n1p2 ext4   3.8T  1.5T  2.1T  42% /",
        stderr="",
        command="sh -c 'df -lH | grep -v 'boot''",
    )

    result, data = collector.collect_data()
    assert result.status == ExecutionStatus.ERROR
    assert data is None

    evt = collector.result.events[0]
    assert evt.category == EventCategory.OS.value
    assert evt.description == "Error checking available storage"
