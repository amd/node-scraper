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
from nodescraper.connection.redfish import RedfishSshProxyConnectionManager

from .analyzer_args import RedfishEventLogAnalyzerArgs
from .collector_args import RedfishEventLogCollectorArgs
from .event_log_analyzer import RedfishEventLogAnalyzer
from .event_log_collector import RedfishEventLogCollector
from .event_log_data import RedfishEventLogDataModel


class RedfishEventLogPlugin(
    OOBandDataPlugin[
        RedfishEventLogDataModel,
        RedfishEventLogCollectorArgs,
        RedfishEventLogAnalyzerArgs,
    ]
):
    """Collect a Redfish LogService's entries (e.g. EventLog) and report Critical/Warning entries.

    Uses RedfishConnectionManager. Set collection_args.log_service_path to the LogService to read.
    """

    DATA_MODEL = RedfishEventLogDataModel
    COLLECTOR = RedfishEventLogCollector
    ANALYZER = RedfishEventLogAnalyzer
    COLLECTOR_ARGS = RedfishEventLogCollectorArgs
    ANALYZER_ARGS = RedfishEventLogAnalyzerArgs


class AmcRedfishEventLogPlugin(RedfishEventLogPlugin):
    """Collect AMC Redfish EventLog entries through the BMC SSH proxy.

    Same collection and analysis as RedfishEventLogPlugin; uses
    RedfishSshProxyConnectionManager so both plugins can run in the same
    node-scraper invocation (BMC EventLog on the direct connection, AMC
    EventLog on the proxy).
    """

    CONNECTION_TYPE = RedfishSshProxyConnectionManager  # type: ignore[assignment]
