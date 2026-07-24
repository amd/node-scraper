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

from pydantic import Field, field_validator

from nodescraper.plugins.serviceability.analyzer_args import ServiceabilityAnalyzerArgs


class Mi4xxServiceabilityAnalyzerArgs(ServiceabilityAnalyzerArgs):
    """Analysis args for Mi4xxServiceabilityPlugin."""

    rf_event_log_uri: str = Field(
        default="/redfish/v1/Systems/Instinct_Accelerators/LogServices/EventLog/Entries",
        description="Redfish URI for the Instinct accelerator event log Entries collection.",
    )
    hub_entry_point: Optional[str] = Field(
        default="amdse",
        description="Registered hub entry point name.",
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
