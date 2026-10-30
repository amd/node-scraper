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
from typing import Any, Optional

from nodescraper.base import RedfishDataCollector
from nodescraper.connection.redfish import RF_MEMBERS, RF_MEMBERS_NEXT_LINK, RF_ODATA_ID
from nodescraper.connection.redfish.ssh_proxy_connection import (
    SshProxyRedfishConnection,
)
from nodescraper.enums import EventCategory, EventPriority, ExecutionStatus
from nodescraper.models import TaskResult

from .collector_args import RedfishInventoryCollectorArgs
from .inventory_data import RedfishInventoryDataModel


def _reference_path(value: Any) -> str:
    """Return a fetchable Redfish path from a link value.

    Args:
        value: An OData id string or a dict containing one.

    Returns:
        The absolute path, or an empty string when the value is not fetchable.
    """
    if isinstance(value, dict):
        value = value.get(RF_ODATA_ID)
    if not isinstance(value, str):
        return ""
    text = value.strip()
    if not text or "#" in text or not text.startswith("/"):
        return ""
    return text.rstrip("/") or "/"


def _member_paths(body: dict) -> list[str]:
    """Return member resource paths from a collection body.

    Args:
        body: A Redfish collection payload.

    Returns:
        Absolute member paths.
    """
    paths: list[str] = []
    for item in body.get(RF_MEMBERS) or []:
        if isinstance(item, dict):
            path = _reference_path(item.get(RF_ODATA_ID))
            if path:
                paths.append(path)
    return paths


def _named_path(body: dict, name: str) -> str:
    """Return one named link from a Redfish resource.

    Args:
        body: A Redfish resource payload.
        name: Property that may hold an OData link.

    Returns:
        The linked path, or an empty string when the property is absent.
    """
    return _reference_path(body.get(name))


class RedfishInventoryCollector(
    RedfishDataCollector[RedfishInventoryDataModel, RedfishInventoryCollectorArgs]
):
    """Collect standard Redfish inventory resources without product-specific validation."""

    DATA_MODEL = RedfishInventoryDataModel

    DOCUMENTATION_COLLECTION_ITEMS: tuple[str, ...] = (
        "GET the Redfish service root and follow standard collection links such as Chassis, "
        "Managers, Systems, TelemetryService, and UpdateService.",
        "Expand collection members and follow Assembly, PowerSubsystem, FruDevices, Memory, "
        "Processors, FirmwareInventory, and metric-report links when the service publishes them.",
        "collection_args.collections and collection_args.member_links append extra property "
        "names to that profile set. Names already in the set are ignored.",
        "Uses the active Redfish connection, including a direct session or the SSH proxy.",
        "An SSH-proxy HTTP 404 for a listed collection member is an empty slot and is not a failure.",
    )

    def collect_data(
        self, args: Optional[RedfishInventoryCollectorArgs] = None
    ) -> tuple[TaskResult, Optional[RedfishInventoryDataModel]]:
        """Collect the selected standard Redfish inventory resources.

        Args:
            args: Profile and optional collection overrides.

        Returns:
            The task result and collected responses, or None when the service root cannot be read.
        """
        collect_args = args or RedfishInventoryCollectorArgs()
        api_root = getattr(self.connection, "api_root", "redfish/v1")
        root_path = "/" + str(api_root).strip("/")
        responses: dict[str, dict] = {}
        seen: set[str] = set()
        found_collections = 0
        missing: list[str] = []

        root = self._fetch(root_path, responses, seen)
        if root is None:
            self.result.message = "No Redfish inventory could be read"
            self.result.status = ExecutionStatus.ERROR
            return self.result, None

        for name in collect_args.selected_collections():
            collection_path = _named_path(root, name)
            if not collection_path:
                missing.append(name)
                continue
            found_collections += 1
            for body in self._fetch_pages(collection_path, responses, seen, collect_args.max_pages):
                self._follow_links(body, responses, seen, collect_args)
                for member_path in _member_paths(body):
                    member = self._fetch(member_path, responses, seen, allow_missing=True)
                    if member is not None:
                        self._follow_links(member, responses, seen, collect_args)

        for name in missing:
            self._log_event(
                category=EventCategory.RUNTIME,
                description=f"Redfish service root has no {name} link",
                priority=EventPriority.WARNING,
                console_log=False,
            )

        data = RedfishInventoryDataModel(responses=responses)
        if found_collections == 0:
            self.result.message = "No requested Redfish inventory collections were present"
            self.result.status = ExecutionStatus.WARNING
            return self.result, data

        self.result.message = f"Collected {len(responses)} Redfish inventory resource(s)"
        self.result.status = ExecutionStatus.OK
        return self.result, data

    def _fetch(
        self,
        path: str,
        responses: dict[str, dict],
        seen: set[str],
        allow_missing: bool = False,
    ) -> Optional[dict]:
        """GET one Redfish path and store a successful object body.

        Args:
            path: Absolute Redfish path.
            responses: Collected bodies keyed by path.
            seen: Paths already requested.
            allow_missing: When True, an SSH-proxy HTTP 404 is an empty slot and is not a warning.

        Returns:
            The JSON object, or None when the GET did not return one.
        """
        if path in seen:
            return responses.get(path)
        seen.add(path)
        res = self._run_redfish_get(path, log_artifact=True)
        if res.success and isinstance(res.data, dict):
            responses[path] = res.data
            self.logger.info("Collected Redfish resource %s", path)
            return res.data
        if (
            allow_missing
            and res.status_code == 404
            and isinstance(self.connection, SshProxyRedfishConnection)
        ):
            return None
        self._log_event(
            category=EventCategory.RUNTIME,
            description=f"Redfish GET failed for {path}: {res.error or 'unknown'}",
            priority=EventPriority.WARNING,
            console_log=True,
        )
        return None

    def _fetch_pages(
        self,
        path: str,
        responses: dict[str, dict],
        seen: set[str],
        max_pages: int,
    ) -> list[dict]:
        """GET a resource and additional collection pages up to max_pages.

        Args:
            path: First page path.
            responses: Collected bodies keyed by path.
            seen: Paths already requested.
            max_pages: Maximum pages to keep.

        Returns:
            Bodies that were read, in page order.
        """
        bodies: list[dict] = []
        current = path
        pages = 0
        while current and pages < max_pages:
            body = self._fetch(current, responses, seen)
            pages += 1
            if body is None:
                break
            bodies.append(body)
            current = _reference_path(body.get(RF_MEMBERS_NEXT_LINK))
        return bodies

    def _follow_links(
        self,
        body: dict,
        responses: dict[str, dict],
        seen: set[str],
        args: RedfishInventoryCollectorArgs,
    ) -> None:
        """Follow configured links and expand one level of their members.

        Args:
            body: Resource that may contain the configured links.
            responses: Collected bodies keyed by path.
            seen: Paths already requested.
            args: Collector args selecting which links to follow.

        Returns:
            None
        """
        for name in args.selected_links():
            link = _named_path(body, name)
            if not link:
                continue
            for linked in self._fetch_pages(link, responses, seen, args.max_pages):
                for member_path in _member_paths(linked):
                    self._fetch(member_path, responses, seen, allow_missing=True)
