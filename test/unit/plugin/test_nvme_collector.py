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

from nodescraper.enums import EventPriority, ExecutionStatus, OSFamily
from nodescraper.enums.systeminteraction import SystemInteractionLevel
from nodescraper.models import TaskResult
from nodescraper.plugins.inband.nvme.nvme_collector import NvmeCollector
from nodescraper.plugins.inband.nvme.nvmedata import NvmeDataModel


@pytest.fixture
def collector(system_info, conn_mock):
    c = NvmeCollector(
        system_info=system_info,
        system_interaction_level=SystemInteractionLevel.PASSIVE,
        connection=conn_mock,
    )
    c._log_event = MagicMock()
    c._run_sut_cmd = MagicMock()
    c.result = TaskResult()
    return c


def test_skips_on_windows(collector):
    collector.system_info = MagicMock(os_family=OSFamily.WINDOWS)
    result, data = collector.collect_data()

    assert result.status == ExecutionStatus.NOT_RAN
    assert data is None
    collector._log_event.assert_called_once()
    assert "Windows" in collector._log_event.call_args.kwargs["description"]


@pytest.mark.skip(reason="No NVME device in testing infrastructure")
def test_successful_collection(collector):
    collector.system_info = MagicMock(os_family=OSFamily.LINUX)

    collector._run_sut_cmd.return_value = MagicMock(exit_code=0, stdout="output")

    result, data = collector.collect_data()

    assert result.status == ExecutionStatus.OK
    assert result.message == "NVMe data successfully collected"
    assert isinstance(data, NvmeDataModel)
    assert collector._run_sut_cmd.call_count == 7
    assert any(
        "Collected NVMe data" in call.kwargs["description"]
        for call in collector._log_event.call_args_list
    )


def test_partial_failures(collector):
    collector.system_info = MagicMock(os_family=OSFamily.LINUX)

    def fake_cmd(cmd, sudo):
        return MagicMock(exit_code=0 if "smart-log" in cmd else 1, stdout="out")

    collector._run_sut_cmd.side_effect = fake_cmd

    result, data = collector.collect_data()

    assert result.status in {ExecutionStatus.OK, ExecutionStatus.ERROR}
    assert collector._log_event.call_count >= 1


@pytest.mark.skip(reason="No NVME device in testing infrastructure")
def test_no_data_collected(collector):
    collector.system_info = MagicMock(os_family=OSFamily.LINUX)

    collector._run_sut_cmd.return_value = MagicMock(exit_code=1, stdout="")

    result, data = collector.collect_data()

    assert result.status == ExecutionStatus.ERROR
    assert data is None
    assert "No NVMe data collected" in result.message
    assert any(
        call.kwargs["priority"] == EventPriority.ERROR
        for call in collector._log_event.call_args_list
    )


def test_get_nvme_devices_filters_partitions(collector):
    fake_ls_output = "\n".join(["nvme0", "nvme0n1", "nvme1", "nvme1n1", "sda", "loop0", "nvme2"])
    collector._run_sut_cmd.return_value = MagicMock(exit_code=0, stdout=fake_ls_output)

    devices = collector._get_nvme_devices()

    assert devices == ["/dev/nvme0", "/dev/nvme1", "/dev/nvme2"]
