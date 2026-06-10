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
from .analyzer_args import SwitchDellAnalyzerArgs
from .switchdelldata import SwitchDellDataModel


class SwitchDellAnalyzer(
    SwitchAnalyzerBase[SwitchDellDataModel],
    DataAnalyzer[SwitchDellDataModel, SwitchDellAnalyzerArgs],
):
    """Check Dell SONiC switch data for errors and warnings.

    Walks every model present in the collected :class:`SwitchDellDataModel` and
    checks each ``error_fields`` / ``warning_fields`` ClassVar.

    Port selection can happen in two places:

    * On :class:`SwitchDellCollector` via its ``ports`` arg -- limits what the
      switch is asked to return.
    * On this analyzer via its own ``ports`` arg -- useful when you want to
      collect everything but only flag issues on a subset of ports.

    Both can be set independently. Filter tokens are slash-separated decimal
    segments (e.g. ``["1/1", "1/31", "1/1/1"]``) optionally prefixed with
    ``Ethernet`` or ``Eth``.
    """

    VENDOR_NAME: ClassVar[str] = "Dell"
    DATA_MODEL = SwitchDellDataModel

    # Dell SONiC port identifier. Accept any ``Eth``-prefixed or bare token
    # consisting of one or more slash-separated decimal segments and
    # normalize to the slash-joined form.
    PORT_NAME_RE: ClassVar[re.Pattern] = re.compile(r"^(?:Eth)?(\d+(?:/\d+)*)$", re.IGNORECASE)
    PORT_FORMAT_HINT: ClassVar[str] = "expected slash-separated decimals (e.g. 'M/S', 'A/B/C')"

    def _walk_system(self, switch_data: SwitchDellDataModel) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []

        for idx, arp_entry in enumerate(switch_data.ip_arp or []):
            findings.extend(
                self._check_model(
                    arp_entry,
                    context={"section": "ip_arp", "index": idx},
                )
            )

        for idx, route_entry in enumerate(switch_data.ip_route or []):
            findings.extend(
                self._check_model(
                    route_entry,
                    context={"section": "ip_route", "index": idx},
                )
            )

        return findings
