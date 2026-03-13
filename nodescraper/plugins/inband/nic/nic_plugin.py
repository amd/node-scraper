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
from nodescraper.base import InBandDataPlugin

from .analyzer_args import NicAnalyzerArgs
from .collector_args import NicCollectorArgs
from .nic_analyzer import NicAnalyzer
from .nic_collector import NicCollector
from .nic_data import NicDataModel


class NicPlugin(InBandDataPlugin[NicDataModel, NicCollectorArgs, NicAnalyzerArgs]):
    """Plugin for collecting niccli (Broadcom) and nicctl (Pensando) command output.

    Data is parsed into structured fields (card_show, cards, port, lif, qos, etc.).
    The analyzer checks Broadcom support_rdma (niccli -dev x nvm -getoption support_rdma -scope 0).
    """

    DATA_MODEL = NicDataModel
    COLLECTOR = NicCollector
    COLLECTOR_ARGS = NicCollectorArgs
    ANALYZER = NicAnalyzer
    ANALYZER_ARGS = NicAnalyzerArgs
