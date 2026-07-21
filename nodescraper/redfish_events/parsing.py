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
"""Redfish event parsing helpers (adapted from Gyanam alert ingest)."""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Optional

UTC = timezone.utc

_TS_RE = re.compile(
    r"(\d{4})-(\d{1,2})-(\d{1,2})[T ](\d{1,2}):(\d{1,2}):(\d{1,2})"
    r"(?:\.(\d+))?\s*(Z|[+-]\d{2}:?\d{2})?"
)


def parse_redfish_timestamp(value: Optional[str]) -> Optional[datetime]:
    """Parse Redfish EventTimestamp / LogEntry Created values."""
    if not value or not isinstance(value, str):
        return None
    s = value.strip()
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
    except (ValueError, AttributeError):
        pass

    match = _TS_RE.search(s)
    if not match:
        return None
    year, mon, day, hour, minute, sec, frac, tz = match.groups()
    try:
        micro = int((frac or "0").ljust(6, "0")[:6])
        dt = datetime(int(year), int(mon), int(day), int(hour), int(minute), int(sec), micro)
    except ValueError:
        return None

    if tz and tz != "Z":
        sign = 1 if tz[0] == "+" else -1
        digits = tz[1:].replace(":", "")
        offset = timedelta(hours=int(digits[:2]), minutes=int(digits[2:4]))
        return dt.replace(tzinfo=timezone(sign * offset))
    return dt.replace(tzinfo=UTC)


def normalize_severity(event: dict) -> tuple[str, bool]:
    """Return severity and whether the field was present on the event."""
    raw = event.get("MessageSeverity") or event.get("Severity")
    if raw:
        return str(raw), True
    return "OK", False


def severity_allowed(
    severity: str,
    present: bool,
    allow_list: Optional[list[str]],
) -> bool:
    """Apply case-insensitive severity filtering."""
    if not present:
        return True
    if not allow_list:
        return True
    allowed = {item.casefold() for item in allow_list}
    return severity.casefold() in allowed
