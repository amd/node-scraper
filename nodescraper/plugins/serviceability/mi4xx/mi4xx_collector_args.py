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

from typing import List, Optional

from pydantic import Field, field_validator, model_validator

from nodescraper.models import CollectorArgs
from nodescraper.plugins.serviceability.time_utils import (
    TimeOperator,
    is_valid_iso_datetime,
)

from .mi4xx_analyzer_args import Mi4xxServiceabilityAnalyzerArgs


class MI4XXCollectorArgs(CollectorArgs):
    """MI4xx / Helios OOB Redfish serviceability collector arguments."""

    rf_event_log_uri: str = Field(
        default_factory=lambda: Mi4xxServiceabilityAnalyzerArgs().resolved_rf_event_log_uri(),
        description="Redfish URI for the Instinct accelerator event log Entries collection.",
    )
    follow_next_link: bool = Field(
        default=True,
        description="If True, follow Members@odata.nextLink up to max_pages; else single GET.",
    )
    max_pages: int = Field(
        default=200,
        ge=1,
        le=10_000,
        description="Safety cap on the number of pages when following event log pagination.",
    )
    top: Optional[int] = Field(
        default=None,
        ge=1,
        description="Most recent N entries via $skip after count probe; None collects full window.",
    )
    reference_time: Optional[str] = Field(
        default=None,
        description=(
            "Optional ISO-8601 date or date-time used with time_operator "
            "(e.g. 2026-05-17 or 2026-05-17T13:01:00)."
        ),
    )
    time_operator: Optional[TimeOperator] = Field(
        default=None,
        description="Comparison operator applied when reference_time is set.",
    )
    rf_assembly_uri_template: Optional[str] = Field(
        default=None,
        description="Optional Redfish URI template containing {device} for chassis Assembly GETs.",
    )
    rf_chassis_devices: Optional[List[str]] = Field(
        default=None,
        description="Optional chassis designations paired with rf_assembly_uri_template.",
    )
    rf_firmware_bundle_uri: Optional[str] = Field(
        default=None,
        description="Optional Redfish URI for firmware bundle inventory.",
    )
    afid_sag_path: Optional[str] = Field(
        default=None,
        description=(
            "Optional AFID_SAG.json path for collector FRU grouping logs. "
            "When omitted, FRU summary logging is skipped."
        ),
    )

    @field_validator("afid_sag_path")
    @classmethod
    def _strip_afid_sag_path(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @field_validator("rf_event_log_uri")
    @classmethod
    def _strip_rf_event_log_uri(cls, value: object) -> str:
        text = str(value).strip()
        if not text:
            raise ValueError("rf_event_log_uri must be a non-empty Redfish URI")
        return text

    @field_validator("reference_time")
    @classmethod
    def _validate_reference_time_iso(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            raise ValueError("reference_time must be a non-empty ISO-8601 string")
        if not is_valid_iso_datetime(text):
            raise ValueError(f"reference_time is not ISO-8601 compliant: {value!r}")
        return text

    @model_validator(mode="after")
    def _reference_time_requires_operator(self) -> MI4XXCollectorArgs:
        has_ref = self.reference_time is not None
        has_op = self.time_operator is not None
        if has_ref != has_op:
            raise ValueError("Provide both reference_time and time_operator, or omit both.")
        return self

    def resolved_event_log_uri(self) -> str:
        """Return the configured event log Entries URI."""
        return str(self.rf_event_log_uri).strip()

    @classmethod
    def default_event_log_uri(cls) -> str:
        """Return the built-in default for rf_event_log_uri from Mi4xxServiceabilityAnalyzerArgs."""
        return Mi4xxServiceabilityAnalyzerArgs().resolved_rf_event_log_uri()

    def resolved_afid_sag_path_for_collection(self) -> Optional[str]:
        """Return AFID_SAG path when set for collector FRU summary logging."""
        return self.afid_sag_path
