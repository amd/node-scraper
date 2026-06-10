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
from .analyzer_args import SwitchAristaAnalyzerArgs
from .switcharistadata import SwitchAristaDataModel


class SwitchAristaAnalyzer(
    SwitchAnalyzerBase[SwitchAristaDataModel],
    DataAnalyzer[SwitchAristaDataModel, SwitchAristaAnalyzerArgs],
):
    """Check Arista switch data for errors and warnings.

    Walks every model present in the collected :class:`SwitchAristaDataModel` and
    checks each ``error_fields`` / ``warning_fields`` ClassVar.

    Port selection can happen in two places:

    * On :class:`SwitchAristaCollector` via its ``ports`` arg -- limits what the
      switch is asked to return.
    * On this analyzer via its own ``ports`` arg -- useful when you want to
      collect everything but only flag issues on a subset of ports.

    Both can be set independently. Filter tokens use the form ``"M/S"``
    (e.g. ``["1/1", "2/1", "17/1"]``).
    """

    VENDOR_NAME: ClassVar[str] = "Arista"
    DATA_MODEL = SwitchAristaDataModel

    # ``M/S`` port identifier (e.g. ``1/1``), with optional ``Ethernet``
    # prefix so both filter tokens (``"1/1"``) and live port names
    # (``"Ethernet1/1"``) normalize to the same canonical key.
    PORT_NAME_RE: ClassVar[re.Pattern] = re.compile(r"^(?:Ethernet)?(\d+)/(\d+)$", re.IGNORECASE)
    PORT_FORMAT_HINT: ClassVar[str] = "expected form 'M/S'"

    def _walk_system(self, switch_data: SwitchAristaDataModel) -> list[dict[str, Any]]:
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
