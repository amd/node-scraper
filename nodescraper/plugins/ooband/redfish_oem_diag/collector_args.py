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
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, model_validator

DEFAULT_TASK_TIMEOUT_S = 1800


class RedfishOemDiagCollectorArgs(BaseModel):
    """Collector/analyzer args for Redfish OEM diagnostic log collection."""

    log_service_path: str = Field(
        default="redfish/v1/Systems/UBB/LogServices/DiagLogs",
        description="Redfish path to the LogService (e.g. DiagLogs).",
    )
    oem_diagnostic_types_allowable: Optional[list[str]] = Field(
        default=None,
        description="Allowable OEM diagnostic types for this architecture/BMC. When set, used for validation and as default for oem_diagnostic_types when empty.",
    )
    oem_diagnostic_types: list[str] = Field(
        default_factory=list,
        description="OEM diagnostic types to collect. When empty and oem_diagnostic_types_allowable is set, defaults to that list.",
    )
    task_timeout_s: int = Field(
        default=DEFAULT_TASK_TIMEOUT_S,
        ge=1,
        le=3600,
        description="Max seconds to wait for each BMC task.",
    )

    @model_validator(mode="after")
    def _default_oem_diagnostic_types(self) -> RedfishOemDiagCollectorArgs:
        if not self.oem_diagnostic_types and self.oem_diagnostic_types_allowable:
            return self.model_copy(
                update={"oem_diagnostic_types": list(self.oem_diagnostic_types_allowable)}
            )
        return self
