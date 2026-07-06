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


class MI3XXDeviceInfo(BaseModel):
    """Device identity with separate board and product fields."""

    board_product_name: Optional[str] = Field(
        default=None,
        description="Board product name (IPMI board information area).",
    )
    board_part_number: Optional[str] = Field(
        default=None,
        description="Board part number.",
    )
    board_serial_number: Optional[str] = Field(
        default=None,
        description="Board serial number.",
    )
    board_manufacturing_date: Optional[str] = Field(
        default=None,
        description=(
            "Board manufacturing date as a rendered string "
            "(not IPMI minutes-since-1996 encoding)."
        ),
    )
    product_name: Optional[str] = Field(
        default=None,
        description="Product name (IPMI product information area).",
    )
    product_part_number: Optional[str] = Field(
        default=None,
        description="Product part or model number.",
    )
    product_serial_number: Optional[str] = Field(
        default=None,
        description="Product serial number.",
    )
    product_version: Optional[str] = Field(
        default=None,
        description="Product version (no board-area equivalent in IPMI FRU).",
    )
    oem_extensions: Dict[str, Any] = Field(
        default_factory=dict,
        description=("Vendor-specific fields: extra board/product data, multirecord, etc."),
    )


class MI3XXResult(BaseModel):
    """Structured serviceability report output."""

    node: Optional[str] = None
    node_scraper_version: Optional[str] = Field(
        default=None,
        description="Version of amd-node-scraper that produced this report.",
    )
    plugin_name: Optional[str] = Field(
        default=None,
        description="Name of the serviceability plugin that produced this report.",
    )
    plugin_version: Optional[str] = Field(
        default=None,
        description="Version of the serviceability plugin that produced this report.",
    )
    reporter_extensions: Dict[str, str] = Field(
        default_factory=dict,
        description="Additional tool versions keyed by name.",
    )
    service_recommendations: Dict[str, List[dict]] = Field(default_factory=dict)
    service_action_definitions: Dict[str, dict] = Field(default_factory=dict)
    afid_sag_metadata: Dict[str, Any] = Field(default_factory=dict)
    node_info: Dict[str, Any] = Field(default_factory=dict)
    extensions: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional implementation-specific fields.",
    )


def build_mi3xx_reporting_version_fields(
    *,
    plugin_name: Optional[str] = None,
    plugin_version: Optional[str] = None,
    node_scraper_version: Optional[str] = None,
    **reporter_extensions: str,
) -> Dict[str, Any]:
    """Build keyword arguments for result versioning fields.

    Args:
        plugin_name: Name of the reporting plugin.
        plugin_version: Version of the reporting plugin.
        node_scraper_version: Node scraper version; defaults to the installed package version.
        reporter_extensions: Additional tool versions as keyword arguments.

    Returns:
        Dictionary of versioning fields for a result model.
    """
    import nodescraper

    return {
        "node_scraper_version": node_scraper_version or nodescraper.__version__,
        "plugin_name": plugin_name,
        "plugin_version": plugin_version,
        "reporter_extensions": dict(reporter_extensions),
    }


class MI3XXDataModel(DataModel):
    """Collected OOB Redfish serviceability data model."""

    collected_data: Dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary keyed payloads from the collector implementation.",
    )
    device_info: Dict[str, MI3XXDeviceInfo] = Field(
        default_factory=dict,
        description="Optional device identity keyed by implementer-defined labels.",
    )
    artifacts: Dict[str, Any] = Field(
        default_factory=dict,
        description="Filename to JSON-serializable payload for log_model output.",
    )
    endpoint: Optional[str] = Field(
        default=None,
        description="Optional host or service endpoint label (not necessarily a BMC).",
    )
    log_path: Optional[str] = None
    result: Optional[MI3XXResult] = None

    def log_model(self, log_path: str) -> None:
        """Write artifact files and a JSON summary under the log directory.

        Args:
            log_path: Directory path for output files.

        Returns:
            None.
        """
        os.makedirs(log_path, exist_ok=True)
        for filename, payload in self.artifacts.items():
            if not filename or not str(filename).strip():
                continue
            artifact_path = os.path.join(log_path, str(filename).strip())
            with open(artifact_path, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2)
        summary_path = os.path.join(log_path, "MI3XX_data.json")
        with open(summary_path, "w", encoding="utf-8") as handle:
            json.dump(
                self.model_dump(
                    exclude={"artifacts"},
                    mode="json",
                ),
                handle,
                indent=2,
            )
