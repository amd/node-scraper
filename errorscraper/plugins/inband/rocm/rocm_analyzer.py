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

from errorscraper.enums import EventCategory, EventPriority, ExecutionStatus
from errorscraper.interfaces import DataAnalyzer
from errorscraper.models import TaskResult

from .analyzer_args import RocmAnalyzerArgs
from .rocmdata import RocmDataModel


class RocmAnalyzer(DataAnalyzer[RocmDataModel, RocmAnalyzerArgs]):
    """Check ROCm matches expected versions"""

    DATA_MODEL = RocmDataModel

    def analyze_data(
        self, data: RocmDataModel, args: Optional[RocmAnalyzerArgs] = None
    ) -> TaskResult:
        # skip check if data not provided in config
        if not args or not args.exp_rocm:
            self.result.message = "Expected ROCm not provided"
            self.result.status = ExecutionStatus.NOT_RAN
            return self.result

        for rocm_version in args.exp_rocm:
            if data.rocm_version == rocm_version:
                self.result.message = "ROCm version matches expected"
                self.result.status = ExecutionStatus.OK
                return self.result

        self.result.message = "ROCm version mismatch!"
        self.result.status = ExecutionStatus.ERROR
        self._log_event(
            category=EventCategory.SW_DRIVER,
            description=f"{self.result.message}",
            data={"expected": args.exp_rocm, "actual": data.rocm_version},
            priority=EventPriority.CRITICAL,
            console_log=True,
        )
        return self.result
