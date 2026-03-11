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
from nodescraper.plugins.ooband.redfish_endpoint import (
    RedfishEndpointAnalyzer,
    RedfishEndpointAnalyzerArgs,
    RedfishEndpointCollector,
    RedfishEndpointCollectorArgs,
    RedfishEndpointDataModel,
    RedfishEndpointPlugin,
)


def test_redfish_endpoint_collector_args_default():
    args = RedfishEndpointCollectorArgs()
    assert args.uris == []


def test_redfish_endpoint_collector_args_uris_stripped():
    args = RedfishEndpointCollectorArgs(uris=["  /redfish/v1  ", "/Systems/1 ", " Chassis "])
    assert args.uris == ["/redfish/v1", "/Systems/1", "Chassis"]


def test_redfish_endpoint_collector_args_uris_empty_list():
    args = RedfishEndpointCollectorArgs(uris=[])
    assert args.uris == []


def test_redfish_endpoint_data_model_default():
    model = RedfishEndpointDataModel()
    assert model.responses == {}


def test_redfish_endpoint_data_model_responses():
    model = RedfishEndpointDataModel(responses={"/redfish/v1": {"Name": "Root"}})
    assert model.responses["/redfish/v1"]["Name"] == "Root"


def test_redfish_endpoint_plugin_class_attributes():
    assert RedfishEndpointPlugin.DATA_MODEL is RedfishEndpointDataModel
    assert RedfishEndpointPlugin.COLLECTOR is RedfishEndpointCollector
    assert RedfishEndpointPlugin.ANALYZER is RedfishEndpointAnalyzer
    assert RedfishEndpointPlugin.COLLECTOR_ARGS is RedfishEndpointCollectorArgs
    assert RedfishEndpointPlugin.ANALYZER_ARGS is RedfishEndpointAnalyzerArgs
