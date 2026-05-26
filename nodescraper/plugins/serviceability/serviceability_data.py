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

import json
import os
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from nodescraper.models import DataModel

from .se_models import AfidEvent, ServiceabilityBlock


class DeviceInfo(BaseModel):
    """Chassis fields from Assembly parsing; extra vendor keys belong in oem_extensions."""

    name: Optional[str] = None
    part_number: Optional[str] = None
    production_date: Optional[str] = None
    serial_number: Optional[str] = None
    version: Optional[str] = None
    oem_extensions: Dict[str, Any] = Field(
        default_factory=dict,
        description="Opaque vendor/product extensions parsed by the concrete collector.",
    )


class ServiceabilityResult(BaseModel):
    """Structured serviceability output (typically populated by a downstream analyzer)."""

    node: Optional[str] = None
    service_recommendations: Dict[str, List[dict]] = {}
    service_action_definitions: Dict[str, dict] = {}
    afid_sag_metadata: Dict[str, Any] = {}
    node_info: Dict[str, Any] = {}


class ServiceabilityDataModel(DataModel):
    """Collected Redfish responses and intermediate serviceability fields."""

    responses: dict[str, Any] = {}
    rf_events: list[Any] = []
    assembly_info: Dict[str, DeviceInfo] = {}
    cper_data: Dict[str, Any] = {}
    component_details: Optional[str] = None
    log_path: Optional[str] = None
    bmc_host: Optional[str] = None
    afid_events: List[AfidEvent] = Field(
        default_factory=list,
        description="Service Hub input; built during analysis when not pre-filled.",
    )
    serviceability: Optional[ServiceabilityBlock] = Field(
        default=None,
        description="ANC-style serviceability block (SE input + output).",
    )
    result: Optional[ServiceabilityResult] = None

    def log_model(self, log_path: str) -> None:
        """Write collector artifacts and optional serviceability.json under log_path."""
        os.makedirs(log_path, exist_ok=True)
        responses_path = os.path.join(log_path, "redfish_responses.json")
        with open(responses_path, "w", encoding="utf-8") as f:
            json.dump(self.responses, f, indent=2)
        if self.cper_data:
            cper_path = os.path.join(log_path, "cper_data.json")
            with open(cper_path, "w", encoding="utf-8") as f:
                json.dump(self.cper_data, f, indent=2)
        if self.serviceability is not None:
            serviceability_path = os.path.join(log_path, "serviceability.json")
            with open(serviceability_path, "w", encoding="utf-8") as f:
                json.dump(
                    self.serviceability.model_dump(mode="json"),
                    f,
                    indent=2,
                )
