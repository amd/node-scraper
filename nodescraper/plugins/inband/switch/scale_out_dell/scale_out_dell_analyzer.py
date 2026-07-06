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

from pydantic import BaseModel

from nodescraper.interfaces import DataAnalyzer

from ..switch_analyzer_base import SwitchAnalyzerBase
from .analyzer_args import ScaleOutDellAnalyzerArgs
from .port_names import PORT_TOKEN_RE
from .scaleoutdelldata import DellPortData, ScaleOutDellDataModel


class ScaleOutDellAnalyzer(
    SwitchAnalyzerBase[ScaleOutDellDataModel],
    DataAnalyzer[ScaleOutDellDataModel, ScaleOutDellAnalyzerArgs],
):
    """Check Dell SONiC switch data for errors and warnings.

    Walks every model in the collected :class:`ScaleOutDellDataModel` and checks
    each ``error_fields`` / ``warning_fields`` ClassVar against an optional
    ``ports`` filter.
    """

    VENDOR_NAME: ClassVar[str] = "Dell"
    DATA_MODEL = ScaleOutDellDataModel

    PORT_NAME_RE: ClassVar[re.Pattern] = PORT_TOKEN_RE
    PORT_FORMAT_HINT: ClassVar[str] = "expected slash-separated decimals (e.g. 'M/S', 'A/B/C')"

    def _walk_system(self, switch_data: ScaleOutDellDataModel) -> list[dict[str, Any]]:
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

    def _extra_port_findings(self, port_name: str, port_data: BaseModel) -> list[dict[str, Any]]:
        if not isinstance(port_data, DellPortData):
            return []

        args = self._analyzer_args
        if not isinstance(args, ScaleOutDellAnalyzerArgs):
            args = ScaleOutDellAnalyzerArgs()

        status = port_data.interface_status
        if status is None:
            return []

        finding = self._port_field_mismatch(
            port_name,
            "interface_status",
            "speed",
            status.speed,
            args.expected_port_speed,
            "DellInterfaceStatus",
        )
        return [finding] if finding else []
