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
from datetime import datetime, timezone
from typing import Any

from nodescraper.connection.inband import TextFileArtifact
from nodescraper.plugins.serviceability.se_models import ServiceabilityBlock
from nodescraper.plugins.serviceability.serviceability_api import (
    split_recommendation_actions,
)
from nodescraper.plugins.serviceability.serviceability_hub_analyzer import (
    ServiceabilityHubAnalyzer,
)

SUMMARY_FILENAME = "summary.json"


class MI4XXAnalyzer(ServiceabilityHubAnalyzer):
    """Build AFID events from collected data and run the configured entry-point hub."""

    DOCUMENTATION_ANALYSIS_ITEMS: tuple[str, ...] = (
        "Builds AFID events from collected Redfish event log members (and optional assembly metadata).",
        "Runs the configured entry-point service hub (hub_entry_point in analysis_args) to produce service recommendations.",
        "When analysis_args.skip_hub is true, only builds AFID events without running the hub.",
        "Supports offline analysis from a prior collection via --data with --collection False.",
        f"Writes the top service action to {SUMMARY_FILENAME} in the analyzer log directory.",
    )

    def _append_hub_artifacts(self, block: ServiceabilityBlock) -> None:
        super()._append_hub_artifacts(block)
        self.result.artifacts.append(
            TextFileArtifact(
                filename=SUMMARY_FILENAME,
                contents=json.dumps(self._top_action_summary(block), indent=2),
            )
        )

    def _top_action_summary(self, block: ServiceabilityBlock) -> dict[str, Any]:
        """Build the summary.json payload for the top Hub service action.

        Args:
            block: Serviceability block returned by the hub.

        Returns:
            System name, analysis time, hub and SAG versions, AFID event count, and the
            top service action(s). Ties for the top rank are all included.
        """
        top, _ = split_recommendation_actions(block)
        return {
            "system_name": self.system_info.name,
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
            "hub_version": block.hub_version,
            "afid_sag_file_version": block.afid_sag_file_version,
            "afid_event_count": len(block.afid_events),
            "top_service_actions": [
                action.model_dump(mode="json", exclude_none=True) for action in top
            ],
        }
