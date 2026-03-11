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

from .analyzer_args import RedfishOemDiagAnalyzerArgs
from .collector_args import RedfishOemDiagCollectorArgs
from .oem_diag_analyzer import RedfishOemDiagAnalyzer
from .oem_diag_collector import RedfishOemDiagCollector
from .oem_diag_data import RedfishOemDiagDataModel


class RedfishOemDiagPlugin(
    OOBandDataPlugin[
        RedfishOemDiagDataModel,
        RedfishOemDiagCollectorArgs,
        RedfishOemDiagAnalyzerArgs,
    ]
):
    """Collect Redfish OEM diagnostic logs (e.g. JournalControl, AllLogs, Dmesg) via LogService.CollectDiagnosticData.

    Uses RedfishConnectionManager. Configure log_service_path, oem_diagnostic_types (and optional output_dir)
    in collection_args; use analysis_args.require_all_success to fail if any type fails.
    """

    DATA_MODEL = RedfishOemDiagDataModel
    COLLECTOR = RedfishOemDiagCollector
    ANALYZER = RedfishOemDiagAnalyzer
    COLLECTOR_ARGS = RedfishOemDiagCollectorArgs
    ANALYZER_ARGS = RedfishOemDiagAnalyzerArgs
