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
from nodescraper.base import OOBandDataPlugin

from .analyzer_args import RedfishEndpointAnalyzerArgs
from .collector_args import RedfishEndpointCollectorArgs
from .endpoint_analyzer import RedfishEndpointAnalyzer
from .endpoint_collector import RedfishEndpointCollector
from .endpoint_data import RedfishEndpointDataModel


class RedfishEndpointPlugin(
    OOBandDataPlugin[
        RedfishEndpointDataModel,
        RedfishEndpointCollectorArgs,
        RedfishEndpointAnalyzerArgs,
    ]
):
    """Config-driven plugin: collect from Redfish URIs and check against thresholds/key-values.

    - RF base address: set via connection config (RedfishConnectionManager).
    - URIs to check: set in collection_args.uris or in a config file (collection_args.config_file).
    - Key/value and threshold checks: set in analysis_args.checks (URI or '*' -> property_path -> constraint).
    """

    DATA_MODEL = RedfishEndpointDataModel
    COLLECTOR = RedfishEndpointCollector
    ANALYZER = RedfishEndpointAnalyzer
    COLLECTOR_ARGS = RedfishEndpointCollectorArgs
    ANALYZER_ARGS = RedfishEndpointAnalyzerArgs
