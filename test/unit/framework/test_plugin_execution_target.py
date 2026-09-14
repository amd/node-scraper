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
from framework.common.shared_utils import DummyDataModel

from nodescraper.base.inbanddataplugin import InBandDataPlugin
from nodescraper.base.oobanddataplugin import OOBandDataPlugin
from nodescraper.enums import SystemLocation
from nodescraper.helpers.plugin_execution_target import (
    format_in_band_target_summary,
    format_plugin_execution_target,
)
from nodescraper.models import SystemInfo


class _DummyOobPlugin(OOBandDataPlugin):
    DATA_MODEL = DummyDataModel


class _DummyInBandPlugin(InBandDataPlugin):
    DATA_MODEL = DummyDataModel


def test_format_in_band_target_summary_local():
    summary = format_in_band_target_summary(SystemInfo(name="workstation01"))
    assert summary == "In-band default: local host (workstation01)"


def test_format_in_band_target_summary_remote():
    summary = format_in_band_target_summary(
        SystemInfo(name="workstation01", location=SystemLocation.REMOTE),
        connection_configs={
            "InBandConnectionManager": {
                "hostname": "ctheliosp-1b112-b34-1.mnb.dcgpu",
            }
        },
    )
    assert summary == "In-band default: remote host via SSH (ctheliosp-1b112-b34-1.mnb.dcgpu)"


def test_format_plugin_execution_target_redfish():
    target = format_plugin_execution_target(
        _DummyOobPlugin,
        system_info=SystemInfo(name="workstation01"),
        connection_configs={
            "RedfishConnectionManager": {"host": "bmc.example.com"},
        },
    )
    assert target == "Execution target: BMC via Redfish OOB (bmc.example.com)"


def test_format_plugin_execution_target_inband_local():
    target = format_plugin_execution_target(
        _DummyInBandPlugin,
        system_info=SystemInfo(name="workstation01", location=SystemLocation.LOCAL),
    )
    assert target == "Execution target: local host (workstation01)"


def test_format_plugin_execution_target_inband_remote():
    target = format_plugin_execution_target(
        _DummyInBandPlugin,
        system_info=SystemInfo(name="workstation01", location=SystemLocation.REMOTE),
        connection_configs={
            "InBandConnectionManager": {"hostname": "sut.example.com"},
        },
    )
    assert target == "Execution target: remote host via SSH (sut.example.com)"
