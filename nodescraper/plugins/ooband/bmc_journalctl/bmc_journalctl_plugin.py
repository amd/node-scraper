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
from nodescraper.base import OOBSSHDataPlugin
from nodescraper.connection.oob_ssh import (
    AmcInBandConnectionManager,
    AmcInBandConnectionParams,
    AmcShellHopConnectionManager,
)
from nodescraper.interfaces import DataPlugin

from .bmc_journalctl_analyzer import JournalctlAnalyzer
from .bmc_journalctl_analyzer_args import JournalctlAnalyzerArgs
from .bmc_journalctl_collector import JournalctlCollector
from .bmc_journalctl_collector_args import JournalctlCollectorArgs
from .bmc_journalctl_data import JournalctlData


class BmcJournalctlPlugin(
    OOBSSHDataPlugin[JournalctlData, JournalctlCollectorArgs, JournalctlAnalyzerArgs]
):
    """Collect BMC journal entries by running journalctl over BMC SSH.

    Uses RedfishConnectionManager for SSH access to the BMC. The collector runs
    journalctl with JSON output and supports multiple collection modes (last_lines,
    since, unit, boot, etc.). The analyzer reports entries at warning level or worse.
    """

    DATA_MODEL = JournalctlData
    COLLECTOR = JournalctlCollector
    COLLECTOR_ARGS = JournalctlCollectorArgs
    ANALYZER = JournalctlAnalyzer
    ANALYZER_ARGS = JournalctlAnalyzerArgs


class AmcJournalctlPlugin(
    DataPlugin[
        AmcInBandConnectionManager,
        AmcInBandConnectionParams,
        JournalctlData,
        JournalctlCollectorArgs,
        JournalctlAnalyzerArgs,
    ]
):
    """Collect AMC journal entries by running journalctl over double-hop SSH (BMC to AMC).

    Uses AmcInBandConnectionManager first. When that tunnel does not connect, collection
    falls back to AmcShellHopConnectionManager, which any plugin can select on its own.
    Same collector and analyzer as BmcJournalctlPlugin, so both plugins can run
    in the same node-scraper invocation.
    """

    CONNECTION_TYPE = AmcInBandConnectionManager
    FALLBACK_CONNECTION_TYPE = AmcShellHopConnectionManager
    DATA_MODEL = JournalctlData
    COLLECTOR = JournalctlCollector
    COLLECTOR_ARGS = JournalctlCollectorArgs
    ANALYZER = JournalctlAnalyzer
    ANALYZER_ARGS = JournalctlAnalyzerArgs
