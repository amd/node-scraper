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

from nodescraper.plugins.serviceability.analyzer_args import ServiceabilityAnalyzerArgs


class Mi4xxServiceabilityAnalyzerArgs(ServiceabilityAnalyzerArgs):
    """Analysis args for Mi4xxServiceabilityPlugin (AFSE entry point)."""

    hub_entry_point: str = Field(
        default="afse",
        description="Registered AFSE entry point name (MI4XX service hub).",
    )
    hub_display_name: Optional[str] = Field(
        default="AFSE",
        description="Label for analyzer status messages.",
    )
    hub_python_module: Optional[str] = Field(
        default=None,
        description="Not used for MI4XX; AFSE is selected via hub_entry_point afse.",
    )
    rf_event_log_uri: str = Field(
        default="/redfish/v1/Systems/Instinct_Accelerators/LogServices/EventLog/Entries",
        description="Redfish URI for the Instinct accelerator event log Entries collection.",
    )

    @field_validator("rf_event_log_uri")
    @classmethod
    def _strip_rf_event_log_uri(cls, value: object) -> str:
        text = str(value).strip()
        if not text:
            raise ValueError("rf_event_log_uri must be a non-empty Redfish URI")
        return text

    def resolved_rf_event_log_uri(self) -> str:
        """Return the configured event log Entries URI."""
        return str(self.rf_event_log_uri).strip()

    @model_validator(mode="after")
    def _mi4xx_uses_afse(self) -> "Mi4xxServiceabilityAnalyzerArgs":
        if self.hub_python_module:
            raise ValueError(
                "Mi4xxServiceabilityPlugin uses AFSE via hub_entry_point; "
                "hub_python_module is not supported"
            )
        if str(self.hub_entry_point).strip().lower() != "afse":
            raise ValueError("Mi4xxServiceabilityPlugin supports hub_entry_point 'afse' only")
        return self
