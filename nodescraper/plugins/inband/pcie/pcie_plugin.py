###############################################################################
#
# MIT License
#
# Copyright (c) 2025 Advanced Micro Devices, Inc.
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
import os
from typing import Any, Optional

from nodescraper.base import InBandDataPlugin

from .analyzer_args import PcieAnalyzerArgs
from .pcie_analyzer import PcieAnalyzer
from .pcie_collector import PcieCollector
from .pcie_data import PcieDataModel


class PciePlugin(InBandDataPlugin[PcieDataModel, None, PcieAnalyzerArgs]):
    """Plugin for collection and analysis of PCIe data"""

    DATA_MODEL = PcieDataModel

    COLLECTOR = PcieCollector

    ANALYZER = PcieAnalyzer

    ANALYZER_ARGS = PcieAnalyzerArgs

    @classmethod
    def load_run_data(cls, run_path: str) -> Optional[dict[str, Any]]:
        """Load inventory compare snapshot for compare-runs diffs.
        Args:
            run_path: Path to a scraper log run directory or datamodel file.
        Returns:
            Inventory snapshot dict, or None when the datamodel is unavailable.
        """
        run_path = os.path.abspath(run_path)
        if not os.path.exists(run_path):
            return None
        dm_path = run_path if os.path.isfile(run_path) else cls.find_datamodel_path_in_run(run_path)
        if not dm_path:
            return None
        data_model = cls.load_datamodel_from_path(dm_path)
        if not isinstance(data_model, PcieDataModel):
            return None
        return data_model.get_compare_snapshot()
