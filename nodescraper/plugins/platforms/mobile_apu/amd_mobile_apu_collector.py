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
from pathlib import Path
from typing import Optional

from nodescraper.base import InBandDataCollector
from nodescraper.enums import ExecutionStatus
from nodescraper.models import TaskResult

from .amd_mobile_apu_data_model import AmdMobileApuDataModel


class AmdMobileApuCollector(InBandDataCollector[AmdMobileApuDataModel, None]):
    DATA_MODEL = AmdMobileApuDataModel

    def _read_int(self, path: str) -> int | None:
        try:
            return int(Path(path).read_text().strip())
        except (OSError, IOError, ValueError):
            return None

    def collect(self) -> AmdMobileApuDataModel:
        pl1_power_limit_mw = self._read_int(
            "/sys/class/powercap/intel-rapl:0/constraint_0_power_limit_uw"
        )
        if pl1_power_limit_mw is not None:
            pl1_power_limit_mw //= 1000

        cpu_temp_millidegree = self._read_int("/sys/class/thermal/thermal_zone0/temp")

        return AmdMobileApuDataModel(
            pl1_power_limit_mw=pl1_power_limit_mw,
            cpu_temp_millidegree=cpu_temp_millidegree,
        )

    def collect_data(
        self, args: Optional[None] = None
    ) -> tuple[TaskResult, Optional[AmdMobileApuDataModel]]:
        return TaskResult(status=ExecutionStatus.OK), self.collect()