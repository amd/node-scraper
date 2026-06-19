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

import base64
from typing import Any, Optional

from nodescraper.plugins.serviceability.serviceability_collector import (
    ServiceabilityCollectorBase,
)
from nodescraper.plugins.serviceability.serviceability_data import DeviceInfo
from nodescraper.plugins.serviceability.time_utils import satisfies_time_check

from .mi3xx_collector_args import MI3XXCollectorArgs
from .mi3xx_cper_utils import RF_CPER_AFID_MIN, should_skip_cper_fetch_or_decode

_EVENT_TIMESTAMP_KEYS = ("Created", "EventTimestamp", "Timestamp")


class MI3XXCollector(ServiceabilityCollectorBase[MI3XXCollectorArgs]):
    """MI3XX OOB Redfish serviceability collector."""

    def satisfies_reference_time(
        self,
        candidate: str,
        args: MI3XXCollectorArgs,
    ) -> bool:
        """Test a timestamp against optional reference-time filter settings."""
        if args.reference_time is None or args.time_operator is None:
            return True
        return satisfies_time_check(candidate, args.reference_time, args.time_operator)

    def filter_event_members(
        self,
        members: list[Any],
        args: MI3XXCollectorArgs,
    ) -> list[Any]:
        filtered: list[Any] = []
        for member in members:
            if not isinstance(member, dict):
                filtered.append(member)
                continue
            timestamp = self._event_timestamp(member)
            if timestamp is None or self.satisfies_reference_time(timestamp, args):
                filtered.append(member)
        return filtered

    def is_cper_event(self, event: dict) -> bool:
        if "CPER" in event:
            return True
        if str(event.get("DiagnosticDataType", "")).upper() == "CPER":
            return True
        if event.get("AdditionalDataURI"):
            return True
        message_id = str(event.get("MessageId", "")).lower()
        message = str(event.get("Message", "")).lower()
        return "cper" in message_id or "cper" in message or "diagnostic" in message_id

    def collect_cper_attachments(self, rf_events: list[Any]) -> dict[str, str]:
        """Fetch CPER binaries from BMC; decoding runs in the analyzer."""
        parent = self.parent or self.__class__.__name__
        attachments: dict[str, str] = {}
        for event in rf_events:
            if not isinstance(event, dict) or not self.is_cper_event(event):
                continue
            uri = event.get("AdditionalDataURI")
            event_id = event.get("Id")
            if not uri or not event_id:
                continue

            if should_skip_cper_fetch_or_decode(event):
                self.logger.info(
                    "(%s) Skipping CPER attachment fetch for Redfish event %s "
                    "(ACA decode already on log entry; AFID<%s check or no serial)",
                    parent,
                    event_id,
                    RF_CPER_AFID_MIN,
                )
                continue

            try:
                resp = self.connection.get_response(uri)
            except Exception as exc:  # noqa: BLE001
                self.logger.warning(
                    "(%s) Failed to fetch CPER attachment for event %s: %s",
                    parent,
                    event_id,
                    exc,
                )
                continue
            if not resp.ok:
                self.logger.warning(
                    "(%s) Failed to fetch CPER attachment for event %s: HTTP %s",
                    parent,
                    event_id,
                    resp.status_code,
                )
                continue

            size_bytes = len(resp.content)
            attachments[str(event_id)] = base64.b64encode(resp.content).decode("ascii")
            self.logger.info(
                "(%s) Fetched CPER attachment for Redfish event %s (%d bytes)",
                parent,
                event_id,
                size_bytes,
            )

        if attachments:
            self.logger.info(
                "(%s) Collected %d CPER attachment(s) for analyzer decode",
                parent,
                len(attachments),
            )
        return attachments

    def parse_assembly_entry(
        self,
        designation: str,
        assembly_member_entry: dict[str, Any],
        args: MI3XXCollectorArgs,
    ) -> DeviceInfo:
        return DeviceInfo(
            name=assembly_member_entry.get("Name") or designation,
            part_number=assembly_member_entry.get("PartNumber"),
            production_date=assembly_member_entry.get("ProductionDate"),
            serial_number=assembly_member_entry.get("SerialNumber"),
            version=assembly_member_entry.get("Version"),
        )

    def extract_component_details(
        self,
        firmware_inventory_payload: dict[str, Any],
        args: MI3XXCollectorArgs,
    ) -> Optional[str]:
        details = firmware_inventory_payload.get("Details")
        if details is not None:
            return str(details)
        return None

    @staticmethod
    def _event_timestamp(event: dict[str, Any]) -> Optional[str]:
        for key in _EVENT_TIMESTAMP_KEYS:
            value = event.get(key)
            if value is not None and str(value).strip():
                return str(value).strip()
        return None
