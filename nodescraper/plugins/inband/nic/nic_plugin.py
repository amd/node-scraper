###############################################################################
#
# MIT License
#
# Copyright (c) 2026 Advanced Micro Devices, Inc.
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
