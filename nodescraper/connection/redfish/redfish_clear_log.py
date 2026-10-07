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
"""Redfish LogService.ClearLog discovery and execution."""

from __future__ import annotations

import logging
from typing import Optional, Sequence

from pydantic import BaseModel

from .redfish_connection import RedfishConnection, RedfishConnectionError
from .redfish_constants import RF_MEMBERS, RF_ODATA_ID

_module_logger = logging.getLogger(__name__)

_ACTION_CLEAR_LOG_KEYS = ("#LogService.ClearLog", "LogService.ClearLog")
_NEVER_OVERWRITE = "NeverOverWrites"

# Redfish DSP0266 standard LogServices sub-resource segment
_LOG_SERVICES_SEGMENT = "LogServices"


class ClearLogEndpoint(BaseModel):
    """A discovered Redfish LogService.ClearLog action endpoint."""

    path: str
    overwrite_policy: str = ""


class ClearLogResult(BaseModel):
    """The result of a single LogService.ClearLog POST."""

    path: str
    success: bool
    status_code: Optional[int] = None
    error: Optional[str] = None


def _odata_id_to_path(odata_id: str, base_url: str) -> str:
    """Normalize an @odata.id value to a relative path (no leading slash).

    Args:
        odata_id: Raw @odata.id string (relative path or full URL).
        base_url: Connection base URL, used to strip the host prefix.

    Returns:
        Relative path with no leading slash, or an empty string if invalid.
    """
    if not odata_id or not isinstance(odata_id, str):
        return ""
    s = odata_id.strip()
    base = base_url.rstrip("/")
    if s.startswith(base + "/"):
        s = s[len(base) :]
    if s.startswith(("http://", "https://")):
        from urllib.parse import urlparse

        s = urlparse(s).path or "/"
    return s.lstrip("/")


def _parse_clear_endpoint(svc_data: dict) -> Optional[ClearLogEndpoint]:
    """Extract a ClearLogEndpoint from a LogService resource body.

    Args:
        svc_data: Parsed LogService JSON body.

    Returns:
        ClearLogEndpoint if the service advertises ClearLog, else None.
    """
    actions = svc_data.get("Actions") or {}
    for key in _ACTION_CLEAR_LOG_KEYS:
        action = actions.get(key)
        if not isinstance(action, dict):
            continue
        target = action.get("target") or ""
        if not target:
            continue
        return ClearLogEndpoint(
            path=target.strip(),
            overwrite_policy=svc_data.get("OverWritePolicy", ""),
        )
    return None


def discover_clear_log_endpoints(
    conn: RedfishConnection,
    roots: Sequence[str] = ("Systems", "Managers"),
    member_ids: Optional[dict[str, list[str]]] = None,
    logger: Optional[logging.Logger] = None,
) -> list[ClearLogEndpoint]:
    """Walk Redfish Systems/Managers LogServices to find ClearLog action endpoints.

    For each root, either walks the collection or uses explicit member IDs.
    Follows the same discovery pattern as ARC's RedfishTool._discover_log_services.

    Args:
        conn: Established Redfish connection.
        roots: Root collections to search ("Systems", "Managers").
        member_ids: Optional map of root → list of member IDs to use directly
            (bypasses the root collection GET). E.g. {"Managers": ["AMC"]}.
        logger: Logger instance.

    Returns:
        List of discovered ClearLogEndpoint objects.
    """
    log = logger or _module_logger
    api_root = (getattr(conn, "api_root", None) or "redfish/v1").strip("/")
    base_url = getattr(conn, "base_url", "")
    endpoints: list[ClearLogEndpoint] = []
    ids_map = member_ids or {}

    for root in roots:
        explicit_ids = ids_map.get(root)
        if explicit_ids is not None:
            members = [{RF_ODATA_ID: f"/{api_root}/{root}/{mid}"} for mid in explicit_ids]
        else:
            try:
                root_data = conn.get_response(f"/{api_root}/{root}")
                if not root_data.ok:
                    log.debug(
                        "LogService discovery: GET %s/%s returned %s",
                        api_root,
                        root,
                        root_data.status_code,
                    )
                    continue
                try:
                    root_body = root_data.json()
                except Exception:
                    continue
                members = (root_body or {}).get(RF_MEMBERS) or []
            except RedfishConnectionError as exc:
                log.debug("LogService discovery: failed to GET %s/%s: %s", api_root, root, exc)
                continue

        for member in members:
            if not isinstance(member, dict):
                continue
            odata_id = member.get(RF_ODATA_ID, "")
            member_path = _odata_id_to_path(odata_id, base_url)
            if not member_path:
                continue

            ls_path = f"/{member_path}/{_LOG_SERVICES_SEGMENT}"
            try:
                ls_resp = conn.get_response(ls_path)
                if not ls_resp.ok:
                    continue
                try:
                    ls_body = ls_resp.json()
                except Exception:
                    continue
            except RedfishConnectionError:
                continue

            for ls_member in (ls_body or {}).get(RF_MEMBERS) or []:
                if not isinstance(ls_member, dict):
                    continue
                ls_odata = ls_member.get(RF_ODATA_ID, "")
                ls_svc_path = _odata_id_to_path(ls_odata, base_url)
                if not ls_svc_path:
                    continue

                try:
                    svc_resp = conn.get_response(f"/{ls_svc_path}")
                    if not svc_resp.ok:
                        continue
                    try:
                        svc_data = svc_resp.json()
                    except Exception:
                        continue
                except RedfishConnectionError:
                    continue

                endpoint = _parse_clear_endpoint(svc_data)
                if endpoint is not None:
                    endpoints.append(endpoint)
                    log.debug(
                        "Discovered ClearLog endpoint: %s (OverWritePolicy=%s)",
                        endpoint.path,
                        endpoint.overwrite_policy,
                    )

    if not endpoints:
        log.debug("No ClearLog endpoints discovered in %s", list(roots))
    return endpoints


def clear_redfish_logs(
    conn: RedfishConnection,
    endpoints: list[ClearLogEndpoint],
    logger: Optional[logging.Logger] = None,
) -> list[ClearLogResult]:
    """POST LogService.ClearLog to each discovered endpoint, skipping NeverOverWrites.

    Mirrors ARC's RedfishTool.clear_log_stores: filters out NeverOverWrites
    stores and continues on individual failures.

    Args:
        conn: Established Redfish connection.
        endpoints: Discovered clear-log endpoints from discover_clear_log_endpoints.
        logger: Logger instance.

    Returns:
        List of ClearLogResult, one per clearable endpoint. Endpoints with
        OverWritePolicy=NeverOverWrites are omitted (not attempted).
    """
    log = logger or _module_logger
    clearable = [e for e in endpoints if e.overwrite_policy != _NEVER_OVERWRITE]
    results: list[ClearLogResult] = []

    for endpoint in clearable:
        path = endpoint.path
        try:
            resp = conn.post(path, json={})
            success = resp.ok
            status_code = resp.status_code
            if success:
                log.debug("Cleared log store: %s (status %s)", path, status_code)
                results.append(ClearLogResult(path=path, success=True, status_code=status_code))
            else:
                body_snippet = ""
                try:
                    body_snippet = resp.text[:300] if resp.text else ""
                except Exception:
                    pass
                error = f"POST {path} returned {status_code}"
                if body_snippet:
                    error = f"{error}: {body_snippet}"
                log.warning("Failed to clear log store %s: %s", path, error)
                results.append(
                    ClearLogResult(path=path, success=False, status_code=status_code, error=error)
                )
        except RedfishConnectionError as exc:
            log.warning("Failed to clear log store %s: %s", path, exc)
            results.append(ClearLogResult(path=path, success=False, error=str(exc)))

    skipped = [e for e in endpoints if e.overwrite_policy == _NEVER_OVERWRITE]
    for endpoint in skipped:
        log.debug("Skipping ClearLog for %s: OverWritePolicy=NeverOverWrites", endpoint.path)

    return results
