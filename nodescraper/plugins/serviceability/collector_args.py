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

from typing import List, Optional, Tuple

from pydantic import Field, field_validator, model_validator

from nodescraper.models import CollectorArgs


class ServiceabilityCollectorArgs(CollectorArgs):
    """Redfish collection arguments for ``ServiceabilityCollectorBase``.

    All Redfish URIs must be supplied by the caller; the base collector does not
    embed product paths. Optional sections (assembly inventory, firmware bundle)
    are skipped when the corresponding URI or template is omitted.
    """

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
        description="Redfish URI for firmware bundle inventory (e.g. ComponentDetails).",
    )
    rf_assembly_fields: Optional[Tuple[str, ...]] = Field(
        default=None,
        description="Standard Assembly JSON field names mapped into ``DeviceInfo``.",
    )
    rf_assembly_oem_fields: Optional[Tuple[str, ...]] = Field(
        default=None,
        description="OEM Assembly field names (under ``Oem``) mapped into ``DeviceInfo``.",
    )
    follow_next_link: bool = Field(
        default=True,
        description=(
            "When True, follow Members@odata.nextLink and merge pages (up to max_pages). "
            "When False, only the first GET response is used."
        ),
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
        description=(
            "Return only the most recent N entries using $skip when the collection "
            "supports OData count; None collects per follow_next_link rules."
        ),
    )
    from_ac_cycle: int = Field(
        default=-1,
        description="Passed to ``filter_event_members`` implementations (e.g. A/C cycle window). -1 disables.",
    )
    from_date: Optional[str] = Field(
        default=None,
        description="Passed to ``filter_event_members`` implementations (e.g. ISO date window).",
    )

    @field_validator("from_ac_cycle")
    @classmethod
    def validate_from_ac_cycle(cls, v: int) -> int:
        if v != -1 and v < 0:
            raise ValueError("from_ac_cycle must be -1 (no filter) or a non-negative integer")
        return v

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
        """Effective event-log URI (``uri`` or ``rf_event_log_uri``)."""
        for candidate in (self.uri, self.rf_event_log_uri):
            if candidate and str(candidate).strip():
                return str(candidate).strip()
        return ""
