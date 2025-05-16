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

from errorscraper.enums.eventpriority import EventPriority
from errorscraper.enums.executionstatus import ExecutionStatus
from errorscraper.enums.systeminteraction import SystemInteractionLevel
from errorscraper.interfaces.task import SystemCompatibilityError
from errorscraper.models.systeminfo import OSFamily
from errorscraper.plugins.inband.cmdline.cmdline_collector import CmdlineCollector
from errorscraper.plugins.inband.cmdline.cmdlinedata import CmdlineDataModel


@pytest.fixture
def collector(system_info, conn_mock):
    return CmdlineCollector(
        system_info=system_info,
        system_interaction_level=SystemInteractionLevel.PASSIVE,
        connection=conn_mock,
    )


def test_run_linux(collector):
    collector._run_sut_cmd = MagicMock(return_value=MagicMock(exit_code=0, stdout="cmdline output"))
    collector._log_event = MagicMock()

    res, data = collector.collect_data()

    assert res.status == ExecutionStatus.OK
    assert data == CmdlineDataModel(cmdline="cmdline output")
    collector._run_sut_cmd.assert_called_once_with("cat /proc/cmdline")
    collector._log_event.assert_called_once_with(
        category="CMDLINE_READ",
        description="cmdline read",
        data={"cmdline": "cmdline output"},
        priority=EventPriority.INFO,
    )


def test_run_windows(system_info, conn_mock):
    system_info.os_family = OSFamily.WINDOWS

    with pytest.raises(SystemCompatibilityError) as e:
        CmdlineCollector(
            system_info=system_info,
            system_interaction_level=SystemInteractionLevel.PASSIVE,
            connection=conn_mock,
        )
    assert str(e.value) == "WINDOWS OS family is not supported"


def test_run_linux_command_error(collector):
    collector._run_sut_cmd = MagicMock(
        return_value=MagicMock(exit_code=1, command="cat /proc/cmdline")
    )

    res, data = collector.collect_data()

    assert res.status == ExecutionStatus.ERROR
    assert data is None
    assert len(res.events) == 1
