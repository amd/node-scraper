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

from datetime import datetime
from typing import Literal

TimeOperator = Literal[">", ">=", "<", "<=", "=="]

_TIME_OPERATORS: set[str] = {">", ">=", "<", "<=", "=="}


def is_valid_iso_datetime(value: str) -> bool:
    """Return whether a string is ISO-8601 compliant.

    Args:
        value: Date or date-time string to validate.

    Returns:
        True if the value parses as ISO-8601.
    """
    try:
        parse_iso_datetime(value)
    except ValueError:
        return False
    return True


def normalize_se_timestamp(value: str) -> str:
    """Normalize a timestamp to the Service Hub wire format.

    Accepts ISO-8601 (``2026-05-07T12:50:42``) and SE-style strings with a space
    separator (``2026-05-07 12:50:42.096-07:00``).
    """
    text = str(value).strip()
    if not text:
        raise ValueError("Empty datetime string")
    if " " in text and "T" not in text:
        return text
    parsed = parse_iso_datetime(text)
    micro = parsed.microsecond
    base = parsed.strftime("%Y-%m-%d %H:%M:%S")
    if micro:
        base = f"{base}.{micro:06d}".rstrip("0").rstrip(".")
    offset = parsed.strftime("%z")
    if offset:
        return f"{base}{offset[:3]}:{offset[3:]}"
    return base


def parse_iso_datetime(value: str) -> datetime:
    """Parse an ISO-8601 or SE-style date-time string.

    Args:
        value: Date (e.g. 2026-05-17), ISO date-time, or SE format with a space separator.

    Returns:
        Parsed datetime.
    """
    text = str(value).strip()
    if not text:
        raise ValueError("Empty datetime string")
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    if " " in text and "T" not in text:
        text = text.replace(" ", "T", 1)
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"Not ISO-8601 compliant: {value!r}") from exc
    if "T" not in value and "+" not in value and value.count("-") == 2:
        return parsed.replace(hour=0, minute=0, second=0, microsecond=0)
    return parsed


def compare_iso_datetime(left: str, right: str, operator: TimeOperator) -> bool:
    """Compare two ISO-8601 values with a relational operator.

    Args:
        left: Left-hand date or date-time string.
        right: Right-hand date or date-time string.
        operator: One of >, >=, <, <=, or ==.

    Returns:
        Result of the comparison.
    """
    if operator not in _TIME_OPERATORS:
        raise ValueError(f"Unsupported time operator: {operator!r}")
    left_dt = parse_iso_datetime(left)
    right_dt = parse_iso_datetime(right)
    if operator == ">":
        return left_dt > right_dt
    if operator == ">=":
        return left_dt >= right_dt
    if operator == "<":
        return left_dt < right_dt
    if operator == "<=":
        return left_dt <= right_dt
    return left_dt == right_dt


def satisfies_time_check(
    candidate: str,
    reference: str,
    operator: TimeOperator,
) -> bool:
    """Test whether candidate satisfies operator against reference.

    Args:
        candidate: Date or date-time string to test.
        reference: Reference date or date-time string.
        operator: One of >, >=, <, <=, or ==.

    Returns:
        True when the comparison holds.
    """
    return compare_iso_datetime(candidate, reference, operator)
