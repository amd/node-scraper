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

from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field

from nodescraper.models import DataModel


def parse_created(value: Optional[str]) -> Optional[datetime]:
    """Parse a LogEntry Created timestamp into an aware datetime.

    Args:
        value: ISO 8601 timestamp, e.g. 2026-01-01T00:00:00+00:00 or ...Z.

    Returns:
        Optional[datetime]: Parsed time (naive values are taken as UTC), or None if unparseable.
    """
    if not value:
        return None
    text = value.strip()
    # Python 3.9's fromisoformat does not accept the "Z" suffix.
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


class EventLogEntry(BaseModel):
    """Subset of a Redfish LogEntry used for analysis."""

    id: str = ""
    odata_id: Optional[str] = None
    created: Optional[str] = None
    severity: Optional[str] = None
    message_id: Optional[str] = None
    message: Optional[str] = None
    message_args: list[str] = Field(default_factory=list)
    entry_type: Optional[str] = None

    @classmethod
    def from_redfish(cls, member: dict[str, Any]) -> EventLogEntry:
        """Build an entry from a LogEntry JSON object.

        Args:
            member: One element of the Entries collection's Members list.

        Returns:
            EventLogEntry: Parsed entry; missing properties are left empty.
        """
        args = member.get("MessageArgs") or []
        return cls(
            id=str(member.get("Id") or ""),
            odata_id=member.get("@odata.id"),
            created=member.get("Created"),
            severity=member.get("Severity"),
            message_id=member.get("MessageId"),
            message=member.get("Message"),
            message_args=[str(a) for a in args] if isinstance(args, list) else [str(args)],
            entry_type=member.get("EntryType"),
        )


class RedfishEventLogDataModel(DataModel):
    """Entries read from one Redfish LogService, newest first."""

    log_service_path: str
    total_count: int = Field(
        default=0,
        description=(
            "Members@odata.count reported on the first page, or the number of entries read "
            "when the service omits it."
        ),
    )
    entries: list[EventLogEntry] = Field(default_factory=list)
