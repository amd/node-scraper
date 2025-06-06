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
from nodescraper.plugins.inband.bios.bios_collector import BiosCollector
from nodescraper.plugins.inband.bios.biosdata import BiosDataModel


@pytest.fixture
def bios_collector(system_info, conn_mock):
    return BiosCollector(
        system_info=system_info,
        system_interaction_level=SystemInteractionLevel.PASSIVE,
        connection=conn_mock,
    )


def test_task_body_windows(system_info, bios_collector):
    """Test the _task_body method on Windows."""
    system_info.os_family = OSFamily.WINDOWS

    bios_collector._run_sut_cmd = MagicMock(
        return_value=MagicMock(
            exit_code=0,
            stdout="\n\nSMBIOSBIOSVersion=TESTBIOS (1.40 )\n\n\n\n",
        )
    )

    exp_data = BiosDataModel(bios_version="TESTBIOS (1.40 )")

    res, data = bios_collector.collect_data()
    assert data == exp_data


def test_task_body_linux(system_info, bios_collector):
    """Test the _task_body method on Linux."""
    system_info.os_family = OSFamily.LINUX

    bios_collector._run_sut_cmd = MagicMock(
        return_value=MagicMock(
            exit_code=0,
            stdout="2.0.1",
        )
    )

    exp_data = BiosDataModel(bios_version="2.0.1")

    res, data = bios_collector.collect_data()
    assert data == exp_data


def test_task_body_error(system_info, bios_collector):
    """Test the _task_body method when an error occurs."""
    system_info.os_family = OSFamily.LINUX

    bios_collector._run_sut_cmd = MagicMock(
        return_value=MagicMock(
            exit_code=1,
            command="sh -c 'dmidecode -s bios-version'",
        )
    )

    res, data = bios_collector.collect_data()
    assert res.status == ExecutionStatus.ERROR
    assert data is None
    assert res.events[0].category == EventCategory.OS.value
    assert res.events[0].description == "Error checking BIOS version"
