###############################################################################
#
# MIT License
#
# Copyright (c) 2025 Advanced Micro Devices, Inc.
#
###############################################################################
from nodescraper.base import InBandDataPlugin

from .analyzer_args import NicCliAnalyzerArgs
from .collector_args import NicCliCollectorArgs
from .niccli_collector import NicCliCollector
from .niccli_data import NicCliDataModel


class NicCliPlugin(InBandDataPlugin[NicCliDataModel, NicCliCollectorArgs, NicCliAnalyzerArgs]):
    """Plugin for collecting niccli (Broadcom) and nicctl (Pensando) command output.

    Use analyzer_args.expected_values (keyed by canonical command key) to check
    what niccli/nicctl commands return; add an analyzer to run those checks.
    """

    DATA_MODEL = NicCliDataModel
    COLLECTOR = NicCliCollector
    COLLECTOR_ARGS = NicCliCollectorArgs
    ANALYZER_ARGS = NicCliAnalyzerArgs
