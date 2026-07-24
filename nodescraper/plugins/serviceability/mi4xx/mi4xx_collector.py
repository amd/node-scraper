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

from typing import Any, Optional

from nodescraper.plugins.serviceability.afid_sag_lookup import log_afid_fru_summary
from nodescraper.plugins.serviceability.event_log_utils import filter_event_log_members
from nodescraper.plugins.serviceability.serviceability_collector import (
    ServiceabilityCollectorBase,
)
from nodescraper.plugins.serviceability.serviceability_data import (
    DeviceInfo,
    ServiceabilityDataModel,
)

from .mi4xx_collector_args import MI4XXCollectorArgs


class MI4XXCollector(ServiceabilityCollectorBase[MI4XXCollectorArgs]):
    """Collect MI4xx BMC Redfish event logs for service hub analysis."""

    DOCUMENTATION_COLLECTION_ITEMS: tuple[str, ...] = (
        "Redfish GET: Instinct accelerator event log Entries (collection_args.rf_event_log_uri).",
        "Paginated Members collection and optional top, reference_time/time_operator filters.",
        "Optional AFID_SAG-backed FRU grouping summary when collection_args.afid_sag_path is set.",
    )

    def _after_collect_data(
        self,
        data: ServiceabilityDataModel,
        args: MI4XXCollectorArgs,
    ) -> None:
        data.afid_sag_path = args.resolved_afid_sag_path_for_collection()
        parent = self.parent or self.__class__.__name__
        log_afid_fru_summary(
            self.logger,
            parent,
            data,
            data.afid_sag_path,
        )

    def filter_event_members(
        self,
        members: list[Any],
        args: MI4XXCollectorArgs,
    ) -> list[Any]:
        return filter_event_log_members(
            members,
            reference_time=args.reference_time,
            time_operator=args.time_operator,
        )

    def is_cper_event(self, event: dict) -> bool:
        return False

    def collect_cper_attachments(self, rf_events: list[Any]) -> dict[str, str]:
        return {}

    def parse_assembly_entry(
        self,
        designation: str,
        assembly_member_entry: dict[str, Any],
        args: MI4XXCollectorArgs,
    ) -> DeviceInfo:
        return DeviceInfo(name=designation)

    def extract_component_details(
        self,
        firmware_inventory_payload: dict[str, Any],
        args: MI4XXCollectorArgs,
    ) -> Optional[str]:
        return None
