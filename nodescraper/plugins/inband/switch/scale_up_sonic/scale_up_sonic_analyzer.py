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
from .analyzer_args import ScaleUpSonicAnalyzerArgs
from .port_names import PORT_TOKEN_RE
from .scaleupsonicdata import ScaleUpSonicDataModel, SonicPortData


class ScaleUpSonicAnalyzer(
    SwitchAnalyzerBase[ScaleUpSonicDataModel],
    DataAnalyzer[ScaleUpSonicDataModel, ScaleUpSonicAnalyzerArgs],
):
    """Check scale up SONiC switch data for errors and warnings.

    Walks every model in the collected :class:`ScaleUpSonicDataModel` and checks
    each ``error_fields`` / ``warning_fields`` ClassVar against an optional
    ``ports`` filter.
    """

    VENDOR_NAME: ClassVar[str] = "SONiC"
    DATA_MODEL = ScaleUpSonicDataModel

    PORT_NAME_RE: ClassVar[re.Pattern] = PORT_TOKEN_RE
    PORT_FORMAT_HINT: ClassVar[str] = "expected 'Ethernet<N>' or '<N>' (e.g. 'Ethernet1', '1')"

    def _extra_port_findings(self, port_name: str, port_data: BaseModel) -> list[dict[str, Any]]:
        if not isinstance(port_data, SonicPortData):
            return []

        args = self._analyzer_args
        if not isinstance(args, ScaleUpSonicAnalyzerArgs):
            args = ScaleUpSonicAnalyzerArgs()

        status = port_data.interface_status
        if status is None:
            return []

        finding = self._port_field_mismatch(
            port_name,
            "interface_status",
            "speed",
            status.speed,
            args.expected_port_speed,
            "SonicInterfaceStatus",
        )
        return [finding] if finding else []
