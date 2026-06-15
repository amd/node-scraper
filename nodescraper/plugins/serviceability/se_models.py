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

from pydantic import BaseModel, Field, field_validator


class AfidEvent(BaseModel):
    """One AFID occurrence on a serviceable unit."""

    afid: int = Field(description="AMD Fault ID.")
    serviceable_unit: str = Field(
        description="Unit label (e.g. gpu02); standardized per platform.",
    )
    time: str = Field(
        description="First-occurrence timestamp (SE format, e.g. 2026-05-07 12:50:42.096-07:00).",
    )

    @field_validator("serviceable_unit")
    @classmethod
    def _strip_serviceable_unit(cls, value: str) -> str:
        text = str(value).strip()
        if not text:
            raise ValueError("serviceable_unit must be non-empty")
        return text


class ServiceabilitySolution(BaseModel):
    """Recommended service action for an AFID."""

    afid: int
    serviceable_unit: List[str] = Field(
        description="Affected serviceable units for this AFID and service action.",
    )
    service_action_num: int = Field(
        description="Service action number from AFID_SAG.json.",
    )
    service_action_title: Optional[str] = Field(
        default=None,
        description=("Short service action label from the hub."),
    )


class ServiceabilityBlock(BaseModel):
    """ANC-style serviceability section: SE input, output, and optional reasoning."""

    afid_events: List[AfidEvent] = Field(
        default_factory=list,
        description="Summarized AFID events from collected data.",
    )
    solution: List[ServiceabilitySolution] = Field(
        default_factory=list,
        description="Hub output: recommended service actions.",
    )
    solution_reasoning: Optional[str] = Field(
        default=None,
        description="Human-readable summary of recommendations (counts and hub label).",
    )
    hub_version: Optional[str] = Field(
        default=None,
        description="Service hub package/build version string when the hub returned it.",
    )
    afid_sag_file_version: Optional[str] = Field(
        default=None,
        description="AFID_SAG.json identity/revision string when the hub returned metadata.",
    )
