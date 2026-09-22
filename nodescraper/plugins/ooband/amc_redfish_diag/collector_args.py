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

from pydantic import BaseModel, Field

from nodescraper.models import CollectorArgs

DEFAULT_TASK_TIMEOUT_S = 1800


class AmcDiagCollectionSpec(BaseModel):
    """One CollectDiagnosticData request for an AMC telemetry bundle."""

    root: str = Field(
        description="Redfish root collection to search: Managers or Systems.",
    )
    diagnostic_data_type: str = Field(
        description="DMTF DiagnosticDataType (Manager, OEM, and similar).",
    )
    oem_data_type: str = Field(
        default="",
        description="OEMDiagnosticDataType when diagnostic_data_type is OEM.",
    )


def _default_collections() -> list[AmcDiagCollectionSpec]:
    """Return the AMC manager dump plus systems AllLogs jobs.

    Returns:
        Default CollectDiagnosticData specs.
    """
    return [
        AmcDiagCollectionSpec(root="Managers", diagnostic_data_type="Manager"),
        AmcDiagCollectionSpec(
            root="Systems",
            diagnostic_data_type="OEM",
            oem_data_type="AllLogs",
        ),
    ]


class AmcRedfishDiagCollectorArgs(CollectorArgs):
    """Collector args for AMC Redfish diagnostic dumps via SSH-proxy curl."""

    manager_ids: list[str] = Field(
        default_factory=lambda: ["AMC"],
        description="Manager member Ids to probe; empty walks the Managers collection.",
    )
    system_ids: list[str] = Field(
        default_factory=lambda: ["MI450", "Accelerators"],
        description="System member Ids to probe; empty walks the Systems collection.",
    )
    collections: list[AmcDiagCollectionSpec] = Field(
        default_factory=_default_collections,
        description="CollectDiagnosticData jobs to run (Managers manager dump then Systems OEM AllLogs).",
    )
    task_timeout_s: int = Field(
        default=DEFAULT_TASK_TIMEOUT_S,
        ge=1,
        le=3600,
        description="Max seconds to wait for each CollectDiagnosticData task.",
    )
