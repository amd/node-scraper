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
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Optional
from urllib.parse import urlparse

from nodescraper.base import RedfishDataCollector
from nodescraper.connection.redfish import RedfishConnection, RedfishGetResult
from nodescraper.enums import EventCategory, EventPriority, ExecutionStatus
from nodescraper.models import TaskResult

from .collector_args import RedfishEndpointCollectorArgs
from .endpoint_data import RedfishEndpointDataModel

ODATA_ID = "@odata.id"
MEMBERS = "Members"


def _normalize_path(odata_id: str, api_root: str) -> str:
    """Convert @odata.id value (URL or path) to a normalized path under api_root."""
    if not odata_id or not isinstance(odata_id, str):
        return ""
    s = odata_id.strip()
    if s.startswith(("http://", "https://")):
        parsed = urlparse(s)
        s = parsed.path or "/"
    if not s.startswith("/"):
        s = "/" + s
    s = s.rstrip("/") or "/"
    api_root_norm = api_root.strip("/")
    if api_root_norm and not s.startswith("/" + api_root_norm):
        return ""
    return s


def _extract_odata_ids(obj: Any) -> list[str]:
    """Recursively extract all @odata.id values from a Redfish JSON body."""
    out: list[str] = []
    if isinstance(obj, dict):
        if ODATA_ID in obj and isinstance(obj[ODATA_ID], str):
            out.append(obj[ODATA_ID])
        for k, v in obj.items():
            if k == MEMBERS and isinstance(v, list):
                for item in v:
                    if (
                        isinstance(item, dict)
                        and ODATA_ID in item
                        and isinstance(item[ODATA_ID], str)
                    ):
                        out.append(item[ODATA_ID])
            elif isinstance(v, dict):
                out.extend(_extract_odata_ids(v))
            elif isinstance(v, list):
                for item in v:
                    if isinstance(item, dict):
                        out.extend(_extract_odata_ids(item))
    return out


def _discover_tree(
    connection: RedfishConnection,
    api_root: str,
    max_depth: int,
    max_endpoints: int,
) -> tuple[list[str], dict[str, dict], list[RedfishGetResult]]:
    """
    Traverse the Redfish resource tree from the service root.
    Returns (sorted paths, path -> JSON body for successful GETs, list of all GET results for artifacts).
    """
    root_path = _normalize_path(api_root, api_root) or ("/" + api_root.strip("/"))
    seen: set[str] = set()
    to_visit: deque[tuple[str, int]] = deque([(root_path, 0)])
    responses: dict[str, dict] = {}
    results: list[RedfishGetResult] = []
    while to_visit:
        if max_endpoints and len(seen) >= max_endpoints:
            break
        path, depth = to_visit.popleft()
        if path in seen or depth > max_depth:
            continue
        seen.add(path)
        res = connection.run_get(path)
        results.append(res)
        if res.success and res.data is not None:
            responses[path] = res.data
            for odata_id in _extract_odata_ids(res.data):
                link_path = _normalize_path(odata_id, api_root)
                if link_path and link_path not in seen and depth + 1 <= max_depth:
                    to_visit.append((link_path, depth + 1))
    return sorted(seen), responses, results


def _uris_from_args(args: Optional[RedfishEndpointCollectorArgs]) -> list[str]:
    """Return list of URIs from collector args.uris."""
    if args is None:
        return []
    return list(args.uris) if args.uris else []


def _fetch_one(connection_copy: RedfishConnection, path: str) -> RedfishGetResult:
    """Run a single GET on a connection copy (used from worker threads)."""
    return connection_copy.run_get(path)


class RedfishEndpointCollector(
    RedfishDataCollector[RedfishEndpointDataModel, RedfishEndpointCollectorArgs]
):
    """Collects Redfish endpoint responses for URIs specified in config."""

    DATA_MODEL = RedfishEndpointDataModel

    def collect_data(
        self, args: Optional[RedfishEndpointCollectorArgs] = None
    ) -> tuple[TaskResult, Optional[RedfishEndpointDataModel]]:
        """GET each configured Redfish URI (or discover from tree); when max_workers > 1, fetches run concurrently."""
        responses: dict[str, dict] = {}
        results: list[RedfishGetResult] = []
        if args and getattr(args, "discover_tree", False):
            api_root = getattr(self.connection, "api_root", "redfish/v1")
            max_depth = getattr(args, "tree_max_depth", 2)
            max_endpoints = getattr(args, "tree_max_endpoints", 0) or 0
            _paths, responses, results = _discover_tree(
                self.connection,
                api_root,
                max_depth=max_depth,
                max_endpoints=max_endpoints,
            )
            for res in results:
                self.result.artifacts.append(res)
                if not res.success and res.error:
                    self._log_event(
                        category=EventCategory.RUNTIME,
                        description=f"Redfish GET failed during tree discovery for {res.path}: {res.error}",
                        priority=EventPriority.WARNING,
                        console_log=True,
                    )
            if not responses:
                self.result.message = "No Redfish endpoints discovered from tree"
                self.result.status = ExecutionStatus.ERROR
                return self.result, None
            data = RedfishEndpointDataModel(responses=responses)
            self.result.message = f"Collected {len(responses)} Redfish endpoint(s) from tree"
            self.result.status = ExecutionStatus.OK
            return self.result, data
        else:
            uris = _uris_from_args(args)
            if not uris:
                self.logger.info(
                    "(RedfishEndpointCollector) No URIs; discover_tree=%s (args=%s). Set discover_tree=true in collection_args to use tree discovery.",
                    getattr(args, "discover_tree", None) if args else None,
                    type(args).__name__ if args else "None",
                )
                self.result.message = "No Redfish URIs configured"
                self.result.status = ExecutionStatus.NOT_RAN
                return self.result, None
            paths = []
            for uri in uris:
                path = uri.strip() if uri else ""
                if not path:
                    continue
                if not path.startswith("/"):
                    path = "/" + path
                paths.append(path)

        max_workers = getattr(args, "max_workers", 1) if args else 1
        max_workers = min(max_workers, len(paths))

        if max_workers <= 1:
            # Sequential
            responses = {}
            for path in paths:
                res = self._run_redfish_get(path, log_artifact=True)
                if res.success and res.data is not None:
                    responses[res.path] = res.data
                else:
                    self._log_event(
                        category=EventCategory.RUNTIME,
                        description=f"Redfish GET failed for {path}: {res.error or 'unknown'}",
                        priority=EventPriority.WARNING,
                        console_log=True,
                    )
        else:
            # Concurrent: one connection copy per worker, collect results in main thread
            responses = {}
            results = []
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {}
                for path in paths:
                    conn = self.connection.copy()
                    futures[executor.submit(_fetch_one, conn, path)] = path
                for future in as_completed(futures):
                    path = futures[future]
                    try:
                        res = future.result()
                        results.append(res)
                        if res.success and res.data is not None:
                            responses[res.path] = res.data
                        else:
                            self._log_event(
                                category=EventCategory.RUNTIME,
                                description=f"Redfish GET failed for {path}: {res.error or 'unknown'}",
                                priority=EventPriority.WARNING,
                                console_log=True,
                            )
                    except Exception as e:
                        self._log_event(
                            category=EventCategory.RUNTIME,
                            description=f"Redfish GET failed for {path}: {e!s}",
                            priority=EventPriority.WARNING,
                            console_log=True,
                        )
            for res in results:
                self.result.artifacts.append(res)

        if not responses:
            self.result.message = "No Redfish endpoints could be read"
            self.result.status = ExecutionStatus.ERROR
            return self.result, None

        data = RedfishEndpointDataModel(responses=responses)
        self.result.message = f"Collected {len(responses)} Redfish endpoint(s)"
        self.result.status = ExecutionStatus.OK
        return self.result, data
