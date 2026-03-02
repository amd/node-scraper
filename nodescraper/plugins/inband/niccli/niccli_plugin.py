###############################################################################
#
# MIT License
#
# Copyright (c) 2025 Advanced Micro Devices, Inc.
#
###############################################################################
from nodescraper.base import InBandDataPlugin

from .analyzer_args import NicAnalyzerArgs
from .collector_args import NicCollectorArgs
from .niccli_collector import NicCollector
from .niccli_data import NicDataModel


class NicPlugin(InBandDataPlugin[NicDataModel, NicCollectorArgs, NicAnalyzerArgs]):
    """Plugin for collecting niccli (Broadcom) and nicctl (Pensando) command output.

    Data is parsed into structured fields (card_show, cards, port, lif, qos, etc.).
    Use analyzer_args.expected_values (keyed by canonical command key) to define
    checks; add an analyzer that uses the structured fields and results to run them.
    """

    DATA_MODEL = NicDataModel
    COLLECTOR = NicCollector
    COLLECTOR_ARGS = NicCollectorArgs
    ANALYZER_ARGS = NicAnalyzerArgs
