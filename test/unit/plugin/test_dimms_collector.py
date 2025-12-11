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
from unittest.mock import MagicMock

import pytest

from nodescraper.enums.eventcategory import EventCategory
from nodescraper.enums.executionstatus import ExecutionStatus
from nodescraper.enums.systeminteraction import SystemInteractionLevel
from nodescraper.models.systeminfo import OSFamily
from nodescraper.plugins.inband.dimm.dimm_collector import DimmCollector
from nodescraper.plugins.inband.dimm.dimmdata import DimmDataModel


@pytest.fixture
def collector(system_info, conn_mock):
    return DimmCollector(
        system_info=system_info,
        system_interaction_level=SystemInteractionLevel.PASSIVE,
        connection=conn_mock,
    )


def test_run_windows(system_info, conn_mock):
    system_info.os_family = OSFamily.WINDOWS
    collector = DimmCollector(
        system_info=system_info,
        system_interaction_level=SystemInteractionLevel.PASSIVE,
        connection=conn_mock,
    )

    collector._run_sut_cmd = MagicMock(
        return_value=MagicMock(
            exit_code=0,
            stdout="8589934592\n8589934592\n17179869184\n",
        )
    )

    result, data = collector.collect_data()
    assert data == DimmDataModel(dimms="32768.00GB @ 2 x 8192.00GB 1 x 16384.00GB ")
    assert result.status == ExecutionStatus.OK


def test_run_linux(collector, system_info):
    system_info.os_family = OSFamily.LINUX

    collector._run_sut_cmd = MagicMock(
        side_effect=[
            MagicMock(
                exit_code=0,
                stdout="Full dmidecode output...",
            ),
            MagicMock(
                exit_code=0,
                stdout="Size: 64 GB\nSize: 64 GB\nSize: 128 GB\n",
            ),
        ]
    )

    result, data = collector.collect_data()

    assert result.status == ExecutionStatus.OK
    assert data == DimmDataModel(dimms="256GB @ 2 x 64GB 1 x 128GB")


def test_run_linux_error(collector, system_info):
    system_info.os_family = OSFamily.LINUX

    collector._run_sut_cmd = MagicMock(
        side_effect=[
            MagicMock(
                exit_code=1,
                stderr="Error occurred",
                command="dmidecode",
            ),
            MagicMock(
                exit_code=1,
                stderr="Error occurred",
                command="sh -c 'dmidecode -t 17 | ...'",
            ),
        ]
    )

    result, data = collector.collect_data()

    assert result.status == ExecutionStatus.ERROR
    assert data is None
    assert result.events[1].category == EventCategory.OS.value
    assert result.events[1].description == "Error checking dimms"
