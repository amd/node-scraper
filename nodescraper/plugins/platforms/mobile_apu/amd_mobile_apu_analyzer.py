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
from typing import Optional

from nodescraper.enums import ExecutionStatus
from nodescraper.interfaces import DataAnalyzer
from nodescraper.models import TaskResult

from .amd_mobile_apu_analyzer_args import AmdMobileApuAnalyzerArgs
from .amd_mobile_apu_data_model import AmdMobileApuDataModel


class AmdMobileApuAnalyzer(DataAnalyzer[AmdMobileApuDataModel, AmdMobileApuAnalyzerArgs]):
    DATA_MODEL = AmdMobileApuDataModel

    def analyze(
        self,
        data_model: AmdMobileApuDataModel,
        analyzer_args: AmdMobileApuAnalyzerArgs | None = None,
    ):
        if data_model.pl1_power_limit_mw is None:
            return {
                "status": "WARN",
                "messages": ["Powercap sensor unavailable (likely WSL or missing kernel module)."],
            }

        actual = data_model.pl1_power_limit_mw
        if analyzer_args and analyzer_args.exp_pl1_power_limit_mw is not None:
            expected = analyzer_args.exp_pl1_power_limit_mw
            if abs(actual - expected) > 1000:
                return {
                    "status": "FAIL",
                    "messages": [f"PL1 mismatch: expected {expected} mW, got {actual} mW"],
                }

        return {"status": "PASS", "messages": []}

    def analyze_data(
        self,
        data: AmdMobileApuDataModel,
        args: Optional[AmdMobileApuAnalyzerArgs] = None,
    ) -> TaskResult:
        result = self.analyze(data, args)
        status_map = {
            "PASS": ExecutionStatus.OK,
            "WARN": ExecutionStatus.WARNING,
            "FAIL": ExecutionStatus.ERROR,
        }
        return TaskResult(status=status_map[result["status"]], message="; ".join(result["messages"]))