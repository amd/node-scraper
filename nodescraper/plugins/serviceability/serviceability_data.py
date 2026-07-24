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
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field

from nodescraper.models import DataModel

from .event_log_utils import rf_events_from_json_payload
from .se_models import AfidEvent, ServiceabilityBlock


class ServiceabilityDataLoadError(ValueError):
    """Raised when a serviceability data path cannot be loaded."""


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
    cper_raw: Dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Base64-encoded CPER attachment bytes keyed by Redfish event Id; "
            "populated during collection and decoded in the analyzer."
        ),
    )
    cper_data: Dict[str, Any] = {}
    component_details: Optional[str] = None
    log_path: Optional[str] = None
    bmc_host: Optional[str] = None
    afid_sag_path: Optional[str] = Field(
        default=None,
        description="Optional AFID_SAG.json path used for FRU summary CSV export.",
    )
    afid_events: List[AfidEvent] = Field(
        default_factory=list,
        description="Service Hub input; built during analysis when not pre-filled.",
    )
    serviceability: Optional[ServiceabilityBlock] = Field(
        default=None,
        description="Serviceability block populated by hub analysis.",
    )
    result: Optional[ServiceabilityResult] = None

    @classmethod
    def import_model(
        cls,
        model_input: Union[dict, str],
    ) -> ServiceabilityDataModel:
        """Load from a file path, ServiceabilityDataModel dict, or Redfish Entries collection JSON."""
        if isinstance(model_input, str):
            path = Path(model_input).expanduser()
            if not path.is_file():
                raise ServiceabilityDataLoadError(
                    f"Serviceability data file not found: {path.resolve()}"
                )
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                raise ServiceabilityDataLoadError(
                    f"Invalid JSON in serviceability data file {path.resolve()}: {exc}"
                ) from exc
            return cls._import_from_payload(payload)

        if isinstance(model_input, dict):
            return cls._import_from_payload(model_input)

        return super().import_model(model_input)

    @classmethod
    def _import_from_payload(cls, payload: Any) -> ServiceabilityDataModel:
        if isinstance(payload, dict) and "rf_events" in payload:
            return cls.model_validate(payload)
        try:
            rf_events, responses = rf_events_from_json_payload(payload)
        except ValueError as exc:
            raise ServiceabilityDataLoadError(str(exc)) from exc
        if isinstance(payload, dict):
            merged = dict(payload)
            merged["rf_events"] = rf_events
            if responses and not merged.get("responses"):
                merged["responses"] = responses
            known = set(cls.model_fields)
            return cls.model_validate({k: v for k, v in merged.items() if k in known})
        return cls(rf_events=rf_events, responses=responses)

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
        from .afid_fru_csv import write_afid_fru_summary_csv

        write_afid_fru_summary_csv(
            self,
            log_path,
            logger=logging.getLogger("nodescraper"),
        )
