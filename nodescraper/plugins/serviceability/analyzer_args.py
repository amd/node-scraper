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

from pydantic import Field, field_validator, model_validator

from nodescraper.models import AnalyzerArgs


class ServiceabilityAnalyzerArgs(AnalyzerArgs):
    """Analyzer args for MI3XX serviceability (Python engine via plugin config)."""

    engine_python_module: Optional[str] = Field(
        default=None,
        description=(
            "Importable Python module providing a service engine class with "
            "get_service_info(rf_events, cper_data=...)."
        ),
    )
    engine_display_name: Optional[str] = Field(
        default=None,
        description="Optional label for analyzer status messages.",
    )
    afid_sag_path: Optional[str] = Field(
        default=None,
        description="Path to AFID_SAG.json.",
    )
    skip_engine: bool = Field(
        default=False,
        description="If True, only build afid_events without running the service engine.",
    )

    @field_validator("afid_sag_path", "engine_python_module", "engine_display_name")
    @classmethod
    def _strip_optional_strings(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @model_validator(mode="after")
    def _require_engine_config_when_running(self) -> ServiceabilityAnalyzerArgs:
        if self.skip_engine:
            return self
        if not self.afid_sag_path:
            raise ValueError("afid_sag_path is required when running the service engine.")
        if not self.engine_python_module:
            raise ValueError("engine_python_module is required when running the service engine.")
        return self
