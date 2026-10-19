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
from nodescraper.connection.redfish import (
    RedfishSshProxyConnectionManager,
    RedfishSshProxyConnectionParams,
)
from nodescraper.interfaces import DataPlugin
from nodescraper.plugins.ooband.redfish_oem_diag.oem_diag_data import (
    RedfishOemDiagDataModel,
)

from .amc_diag_collector import AmcRedfishDiagCollector
from .collector_args import AmcRedfishDiagCollectorArgs


class AmcRedfishDiagPlugin(
    DataPlugin[
        RedfishSshProxyConnectionManager,
        RedfishSshProxyConnectionParams,
        RedfishOemDiagDataModel,
        AmcRedfishDiagCollectorArgs,
        None,
    ]
):
    """AMC CollectDiagnosticData over SSH-proxy Redfish for manager and system diagnostic bundles.

    Collection only, there is no analyzer. Each failed collection logs a WARNING event and the
    collector reports ERROR when no collection succeeded, OK when at least one succeeded.

    Configure RedfishSshProxyConnectionManager: ssh to the BMC, host/port of the AMC Redfish
    URL reachable from that BMC. A targets list collects once per BMC. collection_args selects
    Managers Manager dump and Systems OEM AllLogs.
    """

    CONNECTION_TYPE = RedfishSshProxyConnectionManager
    DATA_MODEL = RedfishOemDiagDataModel
    COLLECTOR = AmcRedfishDiagCollector
    COLLECTOR_ARGS = AmcRedfishDiagCollectorArgs
