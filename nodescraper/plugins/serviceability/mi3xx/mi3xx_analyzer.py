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

from typing import Any, ClassVar

from pydantic import BaseModel, Field

from nodescraper.plugins.serviceability.se_models import ServiceabilityBlock
from nodescraper.plugins.serviceability.serviceability_hub_analyzer import (
    ServiceabilityHubAnalyzer,
)


class AfidSagMetadataArtifact(BaseModel):
    """Hub AFID_SAG metadata snapshot; written to ``afid_sag_metadata.json``."""

    ARTIFACT_LOG_BASENAME: ClassVar[str] = "afid_sag_metadata"

    metadata: dict[str, Any] = Field(default_factory=dict)


class MI3XXAnalyzer(ServiceabilityHubAnalyzer):
    """Build AFID events from collected data and run the configured Python service hub."""

    DOCUMENTATION_ANALYSIS_ITEMS: tuple[str, ...] = (
        "Builds AFID events from collected Redfish event log members (and optional assembly metadata).",
        "Optionally decodes CPER attachments via analysis_args.cper_decode_module before hub analysis.",
        "Runs the configured Python service hub (hub_python_module) to produce service recommendations.",
        "When analysis_args.skip_hub is true, only builds AFID events without running the hub.",
    )

    def _append_hub_artifacts(self, block: ServiceabilityBlock) -> None:
        if block.afid_sag_metadata is None:
            return
        self.result.artifacts.append(
            AfidSagMetadataArtifact(metadata=dict(block.afid_sag_metadata))
        )
