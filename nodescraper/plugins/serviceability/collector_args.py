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

from pydantic import Field, model_validator

from nodescraper.models import CollectorArgs


class ServiceabilityCollectorArgs(CollectorArgs):
    """URIs and pagination only. Subclasses add filtering and OEM-specific options."""

    uri: Optional[str] = Field(
        default=None,
        description="Optional alias for ``rf_event_log_uri`` (non-empty string).",
    )
    rf_event_log_uri: Optional[str] = Field(
        default=None,
        description="Redfish URI for the event log ``Entries`` collection.",
    )
    rf_chassis_devices: Optional[List[str]] = Field(
        default=None,
        description="Chassis designations for Assembly GETs; required with ``rf_assembly_uri_template``.",
    )
    rf_assembly_uri_template: Optional[str] = Field(
        default=None,
        description="Redfish URI template containing ``{device}`` for each chassis Assembly resource.",
    )
    rf_firmware_bundle_uri: Optional[str] = Field(
        default=None,
        description="Redfish URI for firmware bundle inventory when subclasses extract component details.",
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

    @model_validator(mode="after")
    def _require_event_log_uri(self) -> ServiceabilityCollectorArgs:
        if not self.resolved_event_log_uri():
            raise ValueError(
                "Provide a non-empty rf_event_log_uri or uri for the event log collection."
            )
        return self

    @model_validator(mode="after")
    def _assembly_consistency(self) -> ServiceabilityCollectorArgs:
        has_tpl = bool(
            self.rf_assembly_uri_template and "{device}" in self.rf_assembly_uri_template
        )
        has_dev = bool(self.rf_chassis_devices)
        if has_tpl != has_dev:
            raise ValueError(
                "Provide both rf_assembly_uri_template (with '{device}') and rf_chassis_devices, "
                "or omit both to skip assembly collection."
            )
        return self

    def resolved_event_log_uri(self) -> str:
        """Return uri or rf_event_log_uri."""
        for candidate in (self.uri, self.rf_event_log_uri):
            if candidate and str(candidate).strip():
                return str(candidate).strip()
        return ""
