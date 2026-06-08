###############################################################################
#
# MIT License
#
# Copyright (c) 2026 Advanced Micro Devices, Inc.
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

from nodescraper.enums import ExecutionStatus
from nodescraper.enums.systeminteraction import SystemInteractionLevel
from nodescraper.plugins.inband.hsio.ifoe_plugin.ifoe_data import IfoeDataModel
from nodescraper.plugins.inband.hsio.ifoe_plugin.ifoe_driver_collector import (
    IfoeDriverCollector,
)
from nodescraper.plugins.inband.hsio.ifoe_plugin.ifoe_plugin import IfoePlugin


@pytest.fixture
def collector(system_info, conn_mock):
    return IfoeDriverCollector(
        system_info=system_info,
        system_interaction_level=SystemInteractionLevel.PASSIVE,
        connection=conn_mock,
    )


def test_collect_driver_version_success(collector):
    collector._run_sut_cmd = MagicMock(
        return_value=MagicMock(
            exit_code=0,
            stdout="version:        1.2.3\n",
            command=IfoeDriverCollector.CMD_MODINFO_VERSION,
        )
    )

    result, data = collector.collect_data()

    assert result.status == ExecutionStatus.OK
    assert data == IfoeDataModel(driver_version="1.2.3")
    collector._run_sut_cmd.assert_called_once_with(IfoeDriverCollector.CMD_MODINFO_VERSION)


def test_collect_driver_version_missing_field(collector):
    collector._run_sut_cmd = MagicMock(
        return_value=MagicMock(
            exit_code=0,
            stdout="description:    IFoE driver\n",
            command=IfoeDriverCollector.CMD_MODINFO_VERSION,
        )
    )

    result, data = collector.collect_data()

    assert result.status == ExecutionStatus.ERROR
    assert data is None


def test_collect_driver_version_command_failure(collector):
    collector._run_sut_cmd = MagicMock(
        return_value=MagicMock(
            exit_code=1,
            stdout="",
            command=IfoeDriverCollector.CMD_MODINFO_VERSION,
        )
    )

    result, data = collector.collect_data()

    assert result.status == ExecutionStatus.ERROR
    assert data is None


def test_ifoe_plugin_wiring():
    assert IfoePlugin.DATA_MODEL is IfoeDataModel
    assert IfoePlugin.get_collector_classes() == (IfoeDriverCollector,)
