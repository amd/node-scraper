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

from nodescraper.enums.executionstatus import ExecutionStatus
from nodescraper.enums.systeminteraction import SystemInteractionLevel
from nodescraper.interfaces.task import SystemCompatibilityError
from nodescraper.models.systeminfo import OSFamily
from nodescraper.plugins.inband.dkms.dkms_collector import DkmsCollector
from nodescraper.plugins.inband.dkms.dkmsdata import DkmsDataModel


@pytest.fixture
def collector(system_info, conn_mock):
    return DkmsCollector(
        system_info=system_info,
        system_interaction_level=SystemInteractionLevel.PASSIVE,
        connection=conn_mock,
    )


def test_run_linux(collector):
    collector.system_info.os_family = OSFamily.LINUX

    collector._run_sut_cmd = MagicMock()
    collector._run_sut_cmd.side_effect = [
        MagicMock(
            exit_code=0,
            stdout=(
                "amdgpu/6.8.5-2009582.22.04, 5.15.0-117-generic, x86_64: installed\n"
                "amdgpu/6.8.5-2009582.22.04, 5.15.0-91-generic, x86_64: installed"
            ),
        ),
        MagicMock(exit_code=0, stdout="dkms-2.8.7"),
    ]

    result, data = collector.collect_data()

    assert result.status == ExecutionStatus.OK
    expected_data = DkmsDataModel(
        status=(
            "amdgpu/6.8.5-2009582.22.04, 5.15.0-117-generic, x86_64: installed\n"
            "amdgpu/6.8.5-2009582.22.04, 5.15.0-91-generic, x86_64: installed"
        ),
        version="dkms-2.8.7",
    )
    assert data == expected_data


def test_run_windows(conn_mock, system_info):
    system_info.os_family = OSFamily.WINDOWS

    with pytest.raises(SystemCompatibilityError):
        DkmsCollector(
            system_info=system_info,
            system_interaction_level=SystemInteractionLevel.PASSIVE,
            connection=conn_mock,
        )
