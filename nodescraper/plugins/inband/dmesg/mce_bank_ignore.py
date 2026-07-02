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
from typing import Optional, Sequence, Union

_MCE_BANK_RE = re.compile(r"\bMC(?P<bank>\d+)_STATUS\b", re.IGNORECASE)

IgnoreMceBankSpec = Union[int, str]


def parse_ignore_mce_banks(
    spec: Optional[Sequence[IgnoreMceBankSpec]],
) -> frozenset[int]:
    """Expand ignore_mce_banks config entries into a set of MCA bank numbers.

    Args:
        spec: Bank ids, bank ranges like ``\"60-63\"``, or ``None``.

    Returns:
        frozenset[int]: MCA bank numbers to ignore.
    """
    if not spec:
        return frozenset()

    banks: set[int] = set()
    for entry in spec:
        if isinstance(entry, int):
            if entry < 0:
                raise ValueError(f"Invalid MCE bank number: {entry}")
            banks.add(entry)
            continue

        token = str(entry).strip()
        if not token:
            raise ValueError("Empty MCE bank ignore entry")

        if "-" in token:
            start_text, end_text = token.split("-", 1)
            start = int(start_text.strip())
            end = int(end_text.strip())
            if start < 0 or end < 0 or start > end:
                raise ValueError(f"Invalid MCE bank range: {entry}")
            banks.update(range(start, end + 1))
            continue

        bank = int(token)
        if bank < 0:
            raise ValueError(f"Invalid MCE bank number: {entry}")
        banks.add(bank)

    return frozenset(banks)


def extract_mce_bank_from_line(line: str) -> Optional[int]:
    """Return the MCA bank number from a dmesg line, if present.

    Args:
        line: Single dmesg log line.

    Returns:
        Optional[int]: MCA bank number, or None when the line has no MCn_STATUS token.
    """
    match = _MCE_BANK_RE.search(line)
    if match is None:
        return None
    return int(match.group("bank"))


def filter_ignored_mce_bank_lines(content: str, ignore_banks: frozenset[int]) -> str:
    """Drop dmesg lines whose MCA bank is listed in ignore_banks.

    Args:
        content: Full dmesg text.
        ignore_banks: MCA bank numbers to ignore.

    Returns:
        str: Filtered dmesg text with ignored MCA bank lines removed.
    """
    if not ignore_banks:
        return content

    kept_lines: list[str] = []
    for line in content.splitlines():
        bank = extract_mce_bank_from_line(line)
        if bank is not None and bank in ignore_banks:
            continue
        kept_lines.append(line)
    if not kept_lines:
        return ""
    return "\n".join(kept_lines) + ("\n" if content.endswith("\n") else "")
