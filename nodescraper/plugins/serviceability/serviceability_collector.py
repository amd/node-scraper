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

import abc
from typing import Any, Optional
from urllib.parse import urlparse

from nodescraper.base import RedfishDataCollector
from nodescraper.connection.redfish import RF_MEMBERS, RF_MEMBERS_COUNT
from nodescraper.enums import ExecutionStatus
from nodescraper.models import TaskResult

from .collector_args import ServiceabilityCollectorArgs
from .serviceability_data import DeviceInfo, ServiceabilityDataModel


class ServiceabilityCollectorBase(
    RedfishDataCollector[ServiceabilityDataModel, ServiceabilityCollectorArgs],
):
    """Redfish serviceability collection flow with product-specific hooks.

    Subclasses implement event filtering, CPER detection, and CPER attachment handling.
    Redfish URIs come only from :class:`ServiceabilityCollectorArgs`.
    """

    DATA_MODEL = ServiceabilityDataModel

    def __init__(self, **kwargs: Any) -> None:
        self._log_path: Optional[str] = kwargs.get("log_path")
        super().__init__(**kwargs)

    @abc.abstractmethod
    def filter_event_members(
        self,
        members: list[Any],
        args: ServiceabilityCollectorArgs,
    ) -> list[Any]:
        """Return the event list to analyze (e.g. time / A/C window)."""

    @abc.abstractmethod
    def is_cper_event(self, event: dict) -> bool:
        """Return whether a Redfish event entry should be treated as diagnostic-backed."""

    @abc.abstractmethod
    def collect_cper_data(self, rf_events: list[Any]) -> dict[str, Any]:
        """Fetch and decode diagnostic attachments for qualifying events (subclass-defined)."""

    def _fetch_event_log(self, args: ServiceabilityCollectorArgs, uri: str):
        if args.follow_next_link:
            return self._run_redfish_get_paged(uri, max_pages=args.max_pages)
        return self._run_redfish_get(uri, log_artifact=True)

    def collect_data(
        self, args: Optional[ServiceabilityCollectorArgs] = None
    ) -> tuple[TaskResult, Optional[ServiceabilityDataModel]]:
        if args is None:
            self.result.status = ExecutionStatus.NOT_RAN
            self.result.message = "ServiceabilityCollectorArgs are required"
            return self.result, None

        event_uri = args.resolved_event_log_uri()
        if args.top is not None:
            res = self._fetch_top(args, args.top, args.max_pages)
        else:
            res = self._fetch_event_log(args, event_uri)

        if not res.success or res.data is None:
            self.result.status = ExecutionStatus.ERROR
            self.result.message = f"Redfish GET failed for {event_uri}: {res.error}"
            return self.result, None

        members = res.data.get(RF_MEMBERS, [])
        responses = {res.path: res.data}
        raw_base_url = getattr(self.connection, "base_url", None)
        bmc_host = urlparse(raw_base_url).hostname if raw_base_url else None

        try:
            filtered_members = self.filter_event_members(members, args)
        except ValueError as exc:
            self.result.status = ExecutionStatus.ERROR
            self.result.message = f"Event filter failed: {exc}"
            return self.result, None

        assembly_info: dict[str, DeviceInfo] = {}
        tpl = args.rf_assembly_uri_template
        devices = args.rf_chassis_devices
        if tpl and devices:
            std_fields = tuple(args.rf_assembly_fields or ())
            oem_fields = tuple(args.rf_assembly_oem_fields or ())
            std_to_device = {
                "Name": "name",
                "PartNumber": "part_number",
                "ProductionDate": "production_date",
                "SerialNumber": "serial_number",
                "Version": "version",
            }

            for device in devices:
                uri_asm = tpl.format(device=device)
                assembly_res = self._run_redfish_get(uri_asm, log_artifact=True)
                if not assembly_res.success or assembly_res.data is None:
                    continue
                responses[assembly_res.path] = assembly_res.data

                assemblies = assembly_res.data.get("Assemblies", [])
                if not assemblies:
                    continue

                entry = assemblies[0]
                oem = entry.get("Oem", {})
                di_kwargs: dict[str, Any] = {}
                for fname in std_fields:
                    key = std_to_device.get(fname)
                    if key:
                        di_kwargs[key] = entry.get(fname)

                for of in oem_fields:
                    if of == "AssemblyPartNumber":
                        di_kwargs["assembly_part_number"] = oem.get(of)
                    elif of == "AssemblySerialNumber":
                        di_kwargs["assembly_serial_number"] = oem.get(of)

                assembly_info[device] = DeviceInfo(**di_kwargs)

        cper_data = self.collect_cper_data(filtered_members or [])

        data = ServiceabilityDataModel(
            responses=responses,
            rf_events=filtered_members or [],
            assembly_info=assembly_info,
            cper_data=cper_data,
            component_details=self._fetch_component_details(responses, args),
            log_path=self._log_path,
            bmc_host=bmc_host,
        )
        self.result.status = ExecutionStatus.OK
        self.result.message = f"Collected {len(members)} event log member(s)"
        return self.result, data

    def _fetch_component_details(
        self, responses: dict[str, Any], args: ServiceabilityCollectorArgs
    ) -> Optional[str]:
        fw_uri = args.rf_firmware_bundle_uri
        if not fw_uri or not str(fw_uri).strip():
            return None
        fw_uri = str(fw_uri).strip()
        fw_res = self._run_redfish_get(fw_uri, log_artifact=True)
        if not fw_res.success or fw_res.data is None:
            return None
        responses[fw_res.path] = fw_res.data

        oem = fw_res.data.get("Oem", {})
        version_id = oem.get("AMD", oem).get("VersionID", {})
        return version_id.get("ComponentDetails")

    def _fetch_top(self, args: ServiceabilityCollectorArgs, top: int, max_pages: int):
        event_uri = args.resolved_event_log_uri()
        probe = self._run_redfish_get(f"{event_uri}?$top=1", log_artifact=True)
        if not probe.success or probe.data is None:
            return probe

        count = probe.data.get(RF_MEMBERS_COUNT, 0)

        if count <= top:
            return self._fetch_event_log(args, event_uri)

        skip = count - top
        skip_uri = f"{event_uri}?$skip={skip}"
        if args.follow_next_link:
            return self._run_redfish_get_paged(skip_uri, max_pages=max_pages)
        return self._run_redfish_get(skip_uri, log_artifact=True)
