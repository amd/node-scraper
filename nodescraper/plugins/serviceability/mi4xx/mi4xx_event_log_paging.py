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

from typing import TYPE_CHECKING, Any, Optional

from nodescraper.connection.redfish import (
    RF_MEMBERS,
    RF_MEMBERS_COUNT,
    RF_MEMBERS_NEXT_LINK,
    RedfishGetResult,
)

if TYPE_CHECKING:
    from .mi4xx_collector import MI4XXCollector


def _base_event_log_uri(uri: str) -> str:
    """Return the event log collection URI without query parameters."""
    return uri.split("?", 1)[0]


def _reported_member_total(payload: dict[str, Any]) -> Optional[int]:
    """Return Members@odata.count when the BMC reports an integer total."""
    raw = payload.get(RF_MEMBERS_COUNT)
    if isinstance(raw, int):
        return raw
    return None


def fetch_mi4xx_event_log(
    collector: MI4XXCollector,
    uri: str,
    *,
    max_pages: int,
) -> RedfishGetResult:
    """Fetch and merge paginated MI4xx event log pages for collection only.

    Args:
        collector: MI4xx collector instance used for Redfish GET requests.
        uri: Event log collection URI for the first page.
        max_pages: Maximum number of pages to fetch including the first page.

    Returns:
        RedfishGetResult with merged Members across all fetched pages.
    """
    parent = collector.parent or collector.__class__.__name__
    first = collector._run_redfish_get(uri, log_artifact=True)
    if not first.success or first.data is None:
        return first

    merged_members: list[Any] = list(first.data.get(RF_MEMBERS) or [])
    merged_data = dict(first.data)
    reported_total = _reported_member_total(first.data)
    base_uri = _base_event_log_uri(uri)

    pages_fetched = 1
    next_link: Optional[str] = first.data.get(RF_MEMBERS_NEXT_LINK)
    last_status = first.status_code

    while pages_fetched < max_pages:
        if next_link:
            page_path = next_link
        elif reported_total is not None and len(merged_members) < reported_total:
            page_path = f"{base_uri}?$skip={len(merged_members)}"
        else:
            break

        page = collector._run_redfish_get(page_path, log_artifact=True)
        last_status = page.status_code
        if not page.success or page.data is None:
            collector.logger.warning(
                "(%s) MI4xx event log page fetch failed at %s: %s",
                parent,
                page_path,
                page.error,
            )
            break

        page_members = page.data.get(RF_MEMBERS) or []
        if not page_members:
            break

        merged_members.extend(page_members)
        next_link = page.data.get(RF_MEMBERS_NEXT_LINK)
        pages_fetched += 1

        if reported_total is not None and len(merged_members) >= reported_total:
            break

    merged_data[RF_MEMBERS] = merged_members
    if reported_total is not None:
        merged_data[RF_MEMBERS_COUNT] = reported_total
    else:
        merged_data[RF_MEMBERS_COUNT] = len(merged_members)
    merged_data.pop(RF_MEMBERS_NEXT_LINK, None)

    if reported_total is not None and len(merged_members) < reported_total:
        collector.logger.warning(
            "(%s) MI4xx event log pagination incomplete: collected %d of %d reported member(s) across %d page(s)",
            parent,
            len(merged_members),
            reported_total,
            pages_fetched,
        )
    elif pages_fetched > 1:
        collector.logger.info(
            "(%s) MI4xx event log pagination merged %d member(s) across %d page(s)",
            parent,
            len(merged_members),
            pages_fetched,
        )

    return RedfishGetResult(
        path=first.path,
        success=True,
        data=merged_data,
        status_code=last_status,
    )
