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
"""Baseline pull of existing Redfish LogService entries (adapted from Gyanam)."""
from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Optional

import httpx

from .models import EventSource, RedfishEvent
from .parsing import normalize_severity, parse_redfish_timestamp, severity_allowed

logger = logging.getLogger(__name__)

BaselineCallback = Callable[[RedfishEvent], None]
_LOG_ROOTS = ("/redfish/v1/Systems", "/redfish/v1/Managers")
_MAX_PAGES = 20


def _abs(base_url: str, uri: str) -> str:
    if not uri:
        return ""
    if uri.startswith("http://") or uri.startswith("https://"):
        return uri
    return f"{base_url.rstrip('/')}/{uri.lstrip('/')}"


def _extract_origin(entry: dict) -> Optional[str]:
    origin = entry.get("OriginOfCondition")
    if origin is None:
        links = entry.get("Links")
        if isinstance(links, dict):
            origin = links.get("OriginOfCondition")
    if isinstance(origin, dict):
        return origin.get("@odata.id")
    if isinstance(origin, str):
        return origin
    return None


async def _get_json(client: httpx.AsyncClient, url: str) -> Optional[dict]:
    try:
        resp = await client.get(url)
    except Exception as exc:  # noqa: BLE001
        logger.debug("Baseline GET failed for %s: %s", url, type(exc).__name__)
        return None
    if resp.status_code != 200:
        return None
    try:
        return resp.json()
    except Exception:  # noqa: BLE001
        return None


async def _discover_entry_collections(client: httpx.AsyncClient, base_url: str) -> list[str]:
    collections: list[str] = []
    seen: set[str] = set()
    for root in _LOG_ROOTS:
        root_doc = await _get_json(client, _abs(base_url, root))
        if not root_doc:
            continue
        for member in root_doc.get("Members", []):
            member_uri = member.get("@odata.id") if isinstance(member, dict) else None
            if not member_uri:
                continue
            member_doc = await _get_json(client, _abs(base_url, member_uri))
            if not member_doc:
                continue
            ls_ref = member_doc.get("LogServices", {})
            ls_uri = ls_ref.get("@odata.id") if isinstance(ls_ref, dict) else None
            if not ls_uri:
                continue
            ls_doc = await _get_json(client, _abs(base_url, ls_uri))
            if not ls_doc:
                continue
            for ls_member in ls_doc.get("Members", []):
                ls_member_uri = ls_member.get("@odata.id") if isinstance(ls_member, dict) else None
                if not ls_member_uri:
                    continue
                ls_detail = await _get_json(client, _abs(base_url, ls_member_uri))
                if not ls_detail:
                    continue
                entries_ref = ls_detail.get("Entries", {})
                entries_uri = (
                    entries_ref.get("@odata.id") if isinstance(entries_ref, dict) else None
                )
                if entries_uri and entries_uri not in seen:
                    seen.add(entries_uri)
                    collections.append(entries_uri)
    return collections


def order_members_newest_first(members: list, max_entries: int) -> list[dict]:
    dicts = [item for item in members if isinstance(item, dict)]

    def _sort_key(member: dict):
        ts = parse_redfish_timestamp(member.get("Created"))
        if ts is not None:
            return (2, ts.timestamp())
        oid = member.get("@odata.id", "") or ""
        try:
            return (1, float(oid.rstrip("/").split("/")[-1]))
        except (ValueError, IndexError):
            return (0, 0.0)

    dicts.sort(key=_sort_key, reverse=True)
    return dicts[:max_entries]


def _naive_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is not None and dt.tzinfo is not None:
        return dt.astimezone(UTC).replace(tzinfo=None)
    return dt


async def _collect_members(
    client: httpx.AsyncClient,
    base_url: str,
    entries_uri: str,
    max_entries: int,
) -> list[dict]:
    members: list[dict] = []
    seen_ids: set[str] = set()
    visited: set[str] = set()
    uri: Optional[str] = entries_uri
    pages = 0
    while uri:
        if uri in visited:
            break
        visited.add(uri)
        doc = await _get_json(client, _abs(base_url, uri))
        if not doc:
            break
        for member in doc.get("Members", []):
            if not isinstance(member, dict):
                continue
            mid = member.get("@odata.id")
            if mid is not None:
                if mid in seen_ids:
                    continue
                seen_ids.add(mid)
            members.append(member)
        pages += 1
        uri = doc.get("Members@odata.nextLink")
        if len(members) >= max_entries * 3 or pages >= _MAX_PAGES:
            break
    return members


async def pull_baseline_events(
    *,
    target_key: str,
    target_name: str,
    target_host: str,
    base_url: str,
    username: str,
    password: str,
    verify_ssl: bool,
    callback: BaselineCallback,
    severities: Optional[list[str]] = None,
    max_entries_per_log: int = 200,
    timeout: float = 30.0,
) -> int:
    """Pull existing log entries and emit RedfishEvent objects via callback."""
    auth = httpx.BasicAuth(username, password)
    emitted = 0
    try:
        async with httpx.AsyncClient(
            auth=auth,
            verify=verify_ssl,
            timeout=timeout,
            follow_redirects=True,
        ) as client:
            collections = await _discover_entry_collections(client, base_url)
            for entries_uri in collections:
                members = await _collect_members(
                    client,
                    base_url,
                    entries_uri,
                    max_entries_per_log,
                )
                for member in order_members_newest_first(members, max_entries_per_log):
                    entry = member
                    if any(k not in entry for k in ("Message", "Severity", "Created")):
                        ref = member.get("@odata.id")
                        if ref:
                            fetched = await _get_json(client, _abs(base_url, ref))
                            if fetched:
                                entry = fetched
                    if (
                        "Message" not in entry
                        and "Severity" not in entry
                        and "MessageSeverity" not in entry
                    ):
                        continue
                    severity, sev_present = normalize_severity(entry)
                    if not severity_allowed(severity, sev_present, severities):
                        continue
                    source_id = entry.get("@odata.id") or member.get("@odata.id")
                    event = RedfishEvent(
                        target_key=target_key,
                        target_name=target_name,
                        target_host=target_host,
                        severity=severity,
                        message=entry.get("Message", "") or "",
                        message_id=entry.get("MessageId"),
                        event_type=entry.get("EntryType") or "Alert",
                        origin_of_condition=_extract_origin(entry),
                        event_timestamp=_naive_utc(parse_redfish_timestamp(entry.get("Created"))),
                        received_at=datetime.now(UTC),
                        source=EventSource.BASELINE,
                        source_id=source_id,
                        raw=dict(entry),
                    )
                    callback(event)
                    emitted += 1
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Baseline pull failed for %s: %s: %s",
            target_name,
            type(exc).__name__,
            exc,
        )
    if emitted:
        logger.info("Baseline pull for %s emitted %d log entries", target_name, emitted)
    return emitted
