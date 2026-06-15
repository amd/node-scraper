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

from typing import Any, Optional

from pydantic import Field, field_validator, model_validator

from nodescraper.models import AnalyzerArgs


class ServiceabilityAnalyzerArgs(AnalyzerArgs):
    """Analyzer args for serviceability plugins that run a configurable Python hub."""

    engine_python_module: Optional[str] = Field(
        default=None,
        description="Import path for the hub module (class implements engine_analyze_method); hub_options forwards kwargs.",
    )
    engine_display_name: Optional[str] = Field(
        default=None,
        description="Optional label for analyzer status messages.",
    )
    afid_sag_path: Optional[str] = Field(
        default=None,
        description="Path to hub config (e.g. AFID_SAG.json); passed as engine_init_path_kwarg.",
    )
    engine_init_path_kwarg: str = Field(
        default="afid_sag",
        description="Hub __init__ keyword that receives afid_sag_path.",
    )
    engine_analyze_method: str = Field(
        default="get_service_info",
        description="Hub method called with rf_events first (default get_service_info).",
    )
    skip_engine: bool = Field(
        default=False,
        description="If True, only build afid_events without running the service hub.",
    )
    cper_decode_module: Optional[str] = Field(
        default=None,
        description="Module import path for CPER decoding when events include CPER attachments.",
    )
    cper_decode_method: str = Field(
        default="analyze_cper",
        description="Callable on cper_decode_module: file-like CPER in, (return_code, decode_dict) out.",
    )
    hub_options: Optional[dict[str, Any]] = Field(
        default=None,
        description="Extra kwargs for hub __init__ and analyze; collected cper_data overrides cper_data key.",
    )
    from_ac_cycle: int = Field(
        default=-1,
        ge=-1,
        description="from_ac_cycle kwarg for the hub analyze call (merged after hub_options).",
    )
    from_date: Optional[str] = Field(
        default=None,
        description="Optional from_date for the hub analyze call (merged after hub_options).",
    )
    designation_serials: Optional[dict[str, str]] = Field(
        default=None,
        description="Optional designation_serials for the hub analyze call (merged after hub_options).",
    )
    suppress_service_actions: Optional[list[str]] = Field(
        default=None,
        description="Optional suppress_service_actions for the hub analyze call (merged after hub_options).",
    )

    def resolved_hub_options(self) -> dict[str, Any]:
        """Merge hub_options with from_ac_cycle, from_date, designation_serials, and suppress_service_actions."""
        merged = dict(self.hub_options or {})
        merged["from_ac_cycle"] = self.from_ac_cycle
        if self.from_date is not None:
            merged["from_date"] = self.from_date
        if self.designation_serials is not None:
            merged["designation_serials"] = self.designation_serials
        if self.suppress_service_actions is not None:
            merged["suppress_service_actions"] = self.suppress_service_actions
        return merged

    @field_validator("engine_analyze_method", "engine_init_path_kwarg")
    @classmethod
    def _strip_non_empty_hub_hooks(cls, value: str) -> str:
        text = str(value).strip()
        if not text:
            raise ValueError("must not be empty")
        return text

    @field_validator("hub_options", mode="before")
    @classmethod
    def _none_empty_hub_options(cls, value: object) -> Optional[dict[str, Any]]:
        if value is None:
            return None
        if isinstance(value, dict) and not value:
            return None
        return value  # type: ignore[return-value]

    @field_validator("from_date", mode="before")
    @classmethod
    def _strip_from_date(cls, value: object) -> Optional[str]:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @field_validator(
        "afid_sag_path",
        "engine_python_module",
        "engine_display_name",
        "cper_decode_module",
    )
    @classmethod
    def _strip_optional_strings(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @model_validator(mode="after")
    def _require_hub_config_when_running(self) -> ServiceabilityAnalyzerArgs:
        if self.skip_engine:
            return self
        if not self.afid_sag_path:
            raise ValueError("afid_sag_path is required when running the service hub.")
        if not self.engine_python_module:
            raise ValueError("engine_python_module is required when running the service hub.")
        return self
