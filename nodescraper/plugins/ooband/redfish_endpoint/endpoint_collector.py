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
import re
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Optional
from urllib.parse import urlparse

from nodescraper.base import RedfishDataCollector
from nodescraper.connection.redfish import (
    RF_MEMBERS,
    RF_MEMBERS_NEXT_LINK,
    RF_ODATA_ID,
    RedfishConnection,
    RedfishGetResult,
)
from nodescraper.connection.redfish.redfish_clear_log import (
    ClearLogEndpoint,
    ClearLogResult,
    clear_redfish_logs,
)
from nodescraper.enums import (
    EventCategory,
    EventPriority,
    ExecutionStatus,
    SystemInteractionLevel,
)
from nodescraper.models import TaskResult

from .collector_args import RedfishEndpointCollectorArgs
from .endpoint_data import RedfishEndpointDataModel

_REFERENCE_KEYS = frozenset(
    {
        RF_ODATA_ID,
        "Uri",
        "@Redfish.ActionInfo",
        "DataSourceUri",
        "TargetComponentURI",
    }
)
_SKIPPED_REFERENCE_SUBTREES = frozenset({"Oem", "OriginOfCondition"})
# Individual LogServices entry resources, not the Entries collection.
_LOG_ENTRY_URI_RE = re.compile(r"LogServices/.*/Entries/[^/]+$")


def _normalize_path(odata_id: str, api_root: str) -> str:
    """Convert @odata.id value (URL or path) to a normalized path under api_root."""
    if not odata_id or not isinstance(odata_id, str):
        return ""
    s = odata_id.strip()
    if s.startswith(("http://", "https://")):
        parsed = urlparse(s)
        s = parsed.path or "/"
        if parsed.query:
            s = f"{s}?{parsed.query}"
    if not s.startswith("/"):
        s = "/" + s
    s = s.rstrip("/") or "/"
    api_root_norm = api_root.strip("/")
    if api_root_norm and not s.startswith("/" + api_root_norm):
        return ""
    return s


def _is_fetchable_reference(value: Any) -> bool:
    """Return whether a value points at a separate Redfish resource.

    Args:
        value: A candidate Redfish reference.

    Returns:
        True when value is an absolute resource path without a fragment.
    """
    return isinstance(value, str) and value.startswith("/") and "#" not in value


def _extract_odata_ids(obj: Any) -> list[str]:
    """Extract Redfish resource references from a JSON body.

    Args:
        obj: A Redfish JSON value.

    Returns:
        Resource paths and resource ids referenced by the body.
    """
    out: list[str] = []
    if not isinstance(obj, dict):
        return out
    for key, value in obj.items():
        if key in _SKIPPED_REFERENCE_SUBTREES:
            continue
        if key == RF_ODATA_ID and isinstance(value, str):
            out.append(value)
        elif key in _REFERENCE_KEYS and _is_fetchable_reference(value):
            out.append(value)
    for key, value in obj.items():
        if key in _SKIPPED_REFERENCE_SUBTREES:
            continue
        if key == RF_MEMBERS and isinstance(value, list):
            for item in value:
                if isinstance(item, dict) and isinstance(item.get(RF_ODATA_ID), str):
                    out.append(item[RF_ODATA_ID])
        elif isinstance(value, dict):
            out.extend(_extract_odata_ids(value))
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    out.extend(_extract_odata_ids(item))
    return out


def _normalize_next_link(odata_id: Any, api_root: str) -> str:
    """Normalize a collection next link and keep its query string.

    Args:
        odata_id: A Members nextLink value.
        api_root: Redfish service root.

    Returns:
        The path and query under the service root, or an empty string.
    """
    if not isinstance(odata_id, str) or not odata_id.strip():
        return ""
    source = odata_id.strip()
    query = ""
    if source.startswith(("http://", "https://")):
        parsed = urlparse(source)
        source = parsed.path or "/"
        query = f"?{parsed.query}" if parsed.query else ""
    elif "?" in source:
        source, raw_query = source.split("?", 1)
        query = "?" + raw_query
    path = _normalize_path(source, api_root)
    if not path:
        return ""
    return path + query


def _enqueue_tree_links(
    payload: Any,
    depth: int,
    api_root: str,
    max_depth: int,
    seen: set[str],
    to_visit: deque[tuple[str, int]],
    queued: set[str],
    max_log_entry_members: int,
) -> None:
    """Queue child resources linked from one Redfish payload.

    Args:
        payload: Redfish JSON body.
        depth: Depth of the payload that contains the links.
        api_root: Redfish service root.
        max_depth: Maximum resource depth.
        seen: Paths already fetched.
        to_visit: Paths waiting to be fetched.
        queued: Paths already queued in this crawl.
        max_log_entry_members: Maximum log entries from this payload. Zero means no limit.

    Returns:
        None
    """
    candidates: list[str] = []
    for odata_id in _extract_odata_ids(payload):
        if isinstance(odata_id, str) and "#" in odata_id:
            continue
        link_path = _normalize_path(odata_id, api_root)
        if not link_path or link_path in seen or link_path in queued or depth + 1 >= max_depth:
            continue
        candidates.append(link_path)
    unique = list(dict.fromkeys(candidates))
    log_entries = sorted(path for path in unique if _LOG_ENTRY_URI_RE.search(path))
    others = [path for path in unique if not _LOG_ENTRY_URI_RE.search(path)]
    if max_log_entry_members:
        log_entries = log_entries[:max_log_entry_members]
    for link_path in others + log_entries:
        queued.add(link_path)
        to_visit.append((link_path, depth + 1))


def _discover_tree(
    connection: RedfishConnection,
    api_root: str,
    max_depth: int,
    max_endpoints: int,
    max_collection_pages: int = 1,
    max_log_entry_members: int = 0,
) -> tuple[list[str], dict[str, dict], list[RedfishGetResult]]:
    """Traverse the Redfish resource tree from the service root.

    Args:
        connection: Connection used to fetch resources.
        api_root: Redfish service-root path.
        max_depth: Maximum resource depth, where one is only the service root.
        max_endpoints: Maximum resource count, where zero means unlimited.
        max_collection_pages: Maximum pages to retain for each paginated collection.
        max_log_entry_members: Maximum individual log entries taken from each payload.

    Returns:
        Visited paths, successful response bodies, and every GET result.
    """
    root_path = _normalize_path(api_root, api_root) or ("/" + api_root.strip("/"))
    seen: set[str] = set()
    queued: set[str] = {root_path}
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
        if not res.success or not isinstance(res.data, dict):
            continue
        responses[path] = res.data
        _enqueue_tree_links(
            res.data,
            depth,
            api_root,
            max_depth,
            seen,
            to_visit,
            queued,
            max_log_entry_members,
        )
        if max_collection_pages <= 1:
            continue
        next_path = _normalize_next_link(res.data.get(RF_MEMBERS_NEXT_LINK), api_root)
        pages = 1
        while next_path and pages < max_collection_pages:
            if next_path in seen or (max_endpoints and len(seen) >= max_endpoints):
                break
            seen.add(next_path)
            queued.add(next_path)
            page_res = connection.run_get(next_path)
            results.append(page_res)
            pages += 1
            if not page_res.success or not isinstance(page_res.data, dict):
                break
            responses[next_path] = page_res.data
            _enqueue_tree_links(
                page_res.data,
                depth,
                api_root,
                max_depth,
                seen,
                to_visit,
                queued,
                max_log_entry_members,
            )
            next_path = _normalize_next_link(page_res.data.get(RF_MEMBERS_NEXT_LINK), api_root)
    return sorted(seen), responses, results


def _uris_from_args(args: Optional[RedfishEndpointCollectorArgs]) -> list[str]:
    """Return list of URIs from collector args.uris."""
    if args is None:
        return []
    return list(args.uris) if args.uris else []


def _discover_tree_enabled(args: Optional[RedfishEndpointCollectorArgs]) -> bool:
    """True only when tree discovery is explicitly enabled (avoids string/other truthy junk)."""
    if args is None:
        return False
    return getattr(args, "discover_tree", False) is True


def _fetch_one(connection_copy: RedfishConnection, path: str) -> RedfishGetResult:
    """Run a single GET on a connection copy (used from worker threads)."""
    return connection_copy.run_get(path)


def _fetch_one_paged(
    connection_copy: RedfishConnection, path: str, max_pages: int
) -> RedfishGetResult:
    """Run a paged GET on a connection copy, following Members@odata.nextLink (used from worker threads)."""
    return connection_copy.run_get_paged(path, max_pages=max_pages)


class RedfishEndpointCollector(
    RedfishDataCollector[RedfishEndpointDataModel, RedfishEndpointCollectorArgs]
):
    """Collects Redfish endpoint responses for URIs specified in config."""

    DATA_MODEL = RedfishEndpointDataModel

    DOCUMENTATION_COLLECTION_ITEMS: tuple[str, ...] = (
        "Redfish GET: explicit paths from collection_args.uris (parallel when max_workers>1).",
        "Optional paged GET following the Members collection OData nextLink field when follow_next_link is true.",
        "Redfish GET tree: when discover_tree is true, walks from api_root using Redfish resource links. "
        "Oem and OriginOfCondition subtrees are not followed. Collection pages and individual log entries "
        "are capped by collection_args.",
    )

    def collect_data(
        self, args: Optional[RedfishEndpointCollectorArgs] = None
    ) -> tuple[TaskResult, Optional[RedfishEndpointDataModel]]:
        """Collect via tree discovery, or via explicit URIs, or skip if neither is configured."""
        uris = _uris_from_args(args)
        use_tree = _discover_tree_enabled(args)

        # 1) Tree discovery: only when discover_tree is explicitly true
        if use_tree:
            api_root = getattr(self.connection, "api_root", "redfish/v1")
            max_depth = getattr(args, "tree_max_depth", 2) if args else 2
            max_endpoints = (getattr(args, "tree_max_endpoints", 0) or 0) if args else 0
            max_collection_pages = getattr(args, "tree_max_collection_pages", 1) if args else 1
            max_log_entry_members = getattr(args, "tree_max_log_entry_members", 0) if args else 0
            _paths, responses, results = _discover_tree(
                self.connection,
                api_root,
                max_depth=max_depth,
                max_endpoints=max_endpoints,
                max_collection_pages=max_collection_pages,
                max_log_entry_members=max_log_entry_members,
            )
            for res in results:
                self._append_redfish_artifact(res)
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
            self._apply_clear_log_uris(args)
            return self.result, data

        # 2) URI list: when discover_tree is false/absent and uris are provided
        if not uris:
            self.result.message = (
                "No collection mode configured: set collection_args.discover_tree to true "
                "or provide collection_args.uris"
            )
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
        follow_next_link = getattr(args, "follow_next_link", False) is True
        max_pages = getattr(args, "max_pages", 200) if args else 200

        if max_workers <= 1:
            # Sequential
            responses = {}
            for path in paths:
                if follow_next_link:
                    res = self._run_redfish_get_paged(path, max_pages=max_pages, log_artifact=True)
                else:
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
                    if follow_next_link:
                        futures[executor.submit(_fetch_one_paged, conn, path, max_pages)] = path
                    else:
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
                self._append_redfish_artifact(res)

        if not responses:
            self.result.message = "No Redfish endpoints could be read"
            self.result.status = ExecutionStatus.ERROR
            return self.result, None

        data = RedfishEndpointDataModel(responses=responses)
        self.result.message = f"Collected {len(responses)} Redfish endpoint(s)"
        self.result.status = ExecutionStatus.OK
        self._apply_clear_log_uris(args)
        return self.result, data

    def _apply_clear_log_uris(self, args: Optional[RedfishEndpointCollectorArgs]) -> None:
        """POST {} to each URI in args.clear_log_uris (LogService.ClearLog endpoints).

        Skips when system_interaction_level < INTERACTIVE. Failures downgrade
        the overall result to WARNING.

        Args:
            args: Collector args carrying the clear_log_uris list.
        """
        if args is None:
            return
        uris = [u.strip() for u in (args.clear_log_uris or []) if u and u.strip()]
        if not uris:
            return
        if self.system_interaction_level < SystemInteractionLevel.INTERACTIVE:
            self.logger.debug(
                "Skipping log clear: system_interaction_level is %s (requires INTERACTIVE)",
                self.system_interaction_level.name,
            )
            return

        endpoints = [ClearLogEndpoint(path=uri) for uri in uris]
        clear_results: list[ClearLogResult] = clear_redfish_logs(
            self.connection, endpoints, self.logger
        )
        cleared = [r for r in clear_results if r.success]
        failed = [r for r in clear_results if not r.success]
        if cleared:
            self.result.message += f"; cleared {len(cleared)} log store(s)"
        if failed:
            descriptions = "; ".join(f"{r.path}: {r.error}" for r in failed)
            self._log_event(
                category=EventCategory.RUNTIME,
                description=f"Failed to clear {len(failed)} log store(s): {descriptions}",
                priority=EventPriority.WARNING,
                console_log=True,
            )
            if self.result.status == ExecutionStatus.OK:
                self.result.status = ExecutionStatus.WARNING
            self.result.message += f"; {len(failed)} log store(s) failed to clear"
