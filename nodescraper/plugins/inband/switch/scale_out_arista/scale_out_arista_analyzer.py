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

import re
from typing import Any, ClassVar

from nodescraper.interfaces import DataAnalyzer

from ..switch_analyzer_base import SwitchAnalyzerBase
from .analyzer_args import ScaleOutAristaAnalyzerArgs
from .scaleoutaristadata import ScaleOutAristaDataModel


class ScaleOutAristaAnalyzer(
    SwitchAnalyzerBase[ScaleOutAristaDataModel],
    DataAnalyzer[ScaleOutAristaDataModel, ScaleOutAristaAnalyzerArgs],
):
    """Check Arista switch data for errors and warnings.

    Walks every model in the collected :class:`ScaleOutAristaDataModel` and checks
    each ``error_fields`` / ``warning_fields`` ClassVar against an optional
    ``ports`` filter.
    """

    VENDOR_NAME: ClassVar[str] = "Arista"
    DATA_MODEL = ScaleOutAristaDataModel

    PORT_NAME_RE: ClassVar[re.Pattern] = re.compile(r"^(?:Ethernet)?(\d+(?:/\d+)*)$", re.IGNORECASE)
    PORT_FORMAT_HINT: ClassVar[str] = "expected slash-separated decimals (e.g. 'M/S', 'A/B/C')"

    def _walk_system(self, switch_data: ScaleOutAristaDataModel) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []

        if switch_data.system_env is None:
            return findings

        findings.extend(
            self._check_model(
                switch_data.system_env,
                context={"section": "system_env"},
            )
        )

        for idx, psu in enumerate(switch_data.system_env.power_supply_slots or []):
            findings.extend(
                self._check_model(
                    psu,
                    context={
                        "section": "power_supply_slots",
                        "index": idx,
                        "label": psu.label,
                    },
                )
            )

        for idx, fan in enumerate(switch_data.system_env.fan_tray_slots or []):
            findings.extend(
                self._check_model(
                    fan,
                    context={
                        "section": "fan_tray_slots",
                        "index": idx,
                        "label": fan.label,
                    },
                )
            )

        return findings
