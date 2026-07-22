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
from typing import FrozenSet, Optional, Sequence, Union

from nodescraper.base.match_ignore import extract_mce_banks_from_text

_MCE_PRIMARY_START_RE = re.compile(
    r"\[Hardware Error\]:\s*(?:Corrected error|Uncorrected error|Machine check events logged)",
    re.IGNORECASE,
)
_MCE_STATUS_START_RE = re.compile(r"\bMC\d+_STATUS\[", re.IGNORECASE)
_MCE_DETAIL_LINE_RE = re.compile(r"\[Hardware Error\]:")

_MCE_CE_STATUS_RE = re.compile(
    r"\[Hardware Error\]:.*?(?P<cpu>CPU:?\d+).*?MC\d+_STATUS\[[^\]]*\|CE\|[^\]]*\]",
    re.IGNORECASE,
)

_MCE_UC_STATUS_RE = re.compile(
    r"\[Hardware Error\]:.*?(?P<cpu>CPU:?\d+).*?MC\d+_STATUS\[[^\]]*\|UC\|[^\]]*\]",
    re.IGNORECASE,
)

_MCE_CE_STATUS_LINE_RE = re.compile(
    r"\[Hardware Error\]:[^\n]*MC\d+_STATUS\[[^\]]*\|CE\|[^\]]*\][^\n]*",
    re.IGNORECASE,
)

_MCE_UC_STATUS_LINE_RE = re.compile(
    r"\[Hardware Error\]:[^\n]*MC\d+_STATUS\[[^\]]*\|UC\|[^\]]*\][^\n]*",
    re.IGNORECASE,
)

# MCE incident rows only
_MCE_INCIDENT_LINE_RE = re.compile(
    r"\[Hardware Error\]:\s*(?:"
    r"(?:Corrected error|Uncorrected error|Machine check events logged)|"
    r"Machine Check:|"
    r"CPU:?\d|"
    r"MC\d+_STATUS|"
    r"PPIN:|"
    r"IPID:|"
    r"Syndrome:|"
    r"cache level:"
    r")",
    re.IGNORECASE,
)


def compile_mce_ce_status_regex() -> re.Pattern[str]:
    """Return a single-line regex for corrected MCn_STATUS hardware error rows."""
    return _MCE_CE_STATUS_LINE_RE


def compile_mce_uc_status_regex() -> re.Pattern[str]:
    """Return a single-line regex for uncorrected MCn_STATUS hardware error rows."""
    return _MCE_UC_STATUS_LINE_RE


def trim_mce_status_match_content(match: Union[str, list[str]]) -> str:
    """Keep only the MCn_STATUS [Hardware Error] row in match_content."""
    if isinstance(match, list):
        for item in match:
            trimmed = trim_mce_status_match_content(item)
            if _MCE_STATUS_START_RE.search(trimmed):
                return trimmed
        return match[0] if match else ""

    for line in str(match).splitlines():
        ce_match = _MCE_CE_STATUS_LINE_RE.search(line)
        if ce_match:
            return ce_match.group(0)
        uc_match = _MCE_UC_STATUS_LINE_RE.search(line)
        if uc_match:
            return uc_match.group(0)
    return str(match)


def _normalize_cpu_label(cpu: str) -> str:
    return cpu.replace(":", "")


def _add_count(counts: dict[str, int], part: str, amount: int) -> None:
    counts[part] = counts.get(part, 0) + amount


def _is_mce_primary_starter(line: str) -> bool:
    return _MCE_PRIMARY_START_RE.search(line) is not None


def _is_mce_block_starter(line: str, *, in_block: bool) -> bool:
    """Return True when line opens a new MCE incident block."""
    if _is_mce_primary_starter(line):
        return True
    if not in_block and _MCE_STATUS_START_RE.search(line) is not None:
        return True
    return False


def _is_mce_detail_line(line: str) -> bool:
    return _MCE_DETAIL_LINE_RE.search(line) is not None


def _is_mce_incident_line(line: str) -> bool:
    return _MCE_INCIDENT_LINE_RE.search(line) is not None


def _mce_detail_line_indices_in_range(lines: Sequence[str], start: int, end: int) -> set[int]:
    return {index for index in range(start, end) if _is_mce_detail_line(lines[index])}


def _next_non_blank_line_index(lines: Sequence[str], index: int) -> Optional[int]:
    """Return the next non-blank line index after index, or None when none remain."""
    for candidate in range(index + 1, len(lines)):
        if lines[candidate].strip():
            return candidate
    return None


def _is_mce_status_only_starter(line: str) -> bool:
    """Return True when line opens a block via MCn_STATUS without a primary header."""
    return not _is_mce_primary_starter(line) and _MCE_STATUS_START_RE.search(line) is not None


def _has_mce_incident_line_ahead(lines: Sequence[str], start_index: int) -> bool:
    """Return True when another MCE incident [Hardware Error]: row appears before the next block."""
    for idx in range(start_index + 1, len(lines)):
        line = lines[idx]
        if not line.strip():
            continue
        if _is_mce_primary_starter(line):
            return False
        if _is_mce_status_only_starter(line):
            return False
        if _is_mce_incident_line(line):
            return True
        if _is_mce_detail_line(line):
            return False
    return False


def mce_defining_status_line_indices(content: str) -> frozenset[int]:
    """Return line indices for MCn_STATUS rows that define a corrected or uncorrected MCE."""
    lines = content.splitlines()
    indices: set[int] = set()
    for index, line in enumerate(lines):
        if _MCE_CE_STATUS_LINE_RE.search(line) or _MCE_UC_STATUS_LINE_RE.search(line):
            indices.add(index)
    return frozenset(indices)


def mce_hardware_error_line_indices(content: str) -> frozenset[int]:
    """Return every line index containing [Hardware Error]:."""
    lines = content.splitlines()
    return frozenset(index for index, line in enumerate(lines) if _is_mce_detail_line(line))


def mce_non_status_hardware_error_line_indices(content: str) -> frozenset[int]:
    """Return [Hardware Error]: detail lines that are not defining MCn_STATUS CE/UC rows."""
    defining = mce_defining_status_line_indices(content)
    return frozenset(
        index for index in mce_hardware_error_line_indices(content) if index not in defining
    )


def _primary_starters_in_mce_status_blocks(
    lines: Sequence[str], defining: frozenset[int]
) -> frozenset[int]:
    """Return primary MCE header lines that belong to blocks with MCn_STATUS CE/UC rows."""
    primary_starters = {index for index, line in enumerate(lines) if _is_mce_primary_starter(line)}
    suppressed: set[int] = set()
    for start, end in iter_hardware_error_block_ranges(lines):
        if any(index in defining for index in range(start, end)):
            suppressed.update(index for index in range(start, end) if index in primary_starters)
    return frozenset(suppressed)


def mce_known_regex_skip_line_indices(
    content: str,
    ignore_banks: Optional[FrozenSet[int]] = None,
) -> frozenset[int]:
    """Skip non-defining MCE detail lines and ignored-bank incidents during known regex scan."""
    ignored = ignore_banks or frozenset()
    lines = content.splitlines()
    defining = mce_defining_status_line_indices(content)
    primary_starters = frozenset(
        index for index, line in enumerate(lines) if _is_mce_primary_starter(line)
    )
    primary_in_status_blocks = _primary_starters_in_mce_status_blocks(lines, defining)
    skipped = set(hardware_error_block_line_indices(content)) - defining - primary_starters
    skipped.update(primary_in_status_blocks)
    skipped.update(ignored_mce_block_line_indices(content, ignored))
    return frozenset(skipped)


def mce_unknown_suppress_line_indices(content: str) -> frozenset[int]:
    """Suppress MCE block context and every [Hardware Error]: line from unknown scan."""
    suppressed = set(mce_block_all_line_indices(content))
    suppressed.update(mce_hardware_error_line_indices(content))
    return frozenset(suppressed)


def iter_hardware_error_block_ranges(lines: Sequence[str]) -> list[tuple[int, int]]:
    """Return (start, end) line index ranges for MCE incident blocks.

    A block begins at a primary MCE header (Corrected/Uncorrected/Machine check logged)
    or at the first MCn_STATUS line when not already inside a block. The block then
    includes subsequent lines until the next primary header, a blank line before a bare
    MCn_STATUS starter, a non-MCE [Hardware Error]: row, trailing lines with no further
    MCE incident detail, or EOF. Blank lines, warn/err noise, and other non-MCE dmesg
    lines between MCE incident entries belong to the same block.
    """
    blocks: list[tuple[int, int]] = []
    index = 0
    total = len(lines)
    while index < total:
        if not _is_mce_block_starter(lines[index], in_block=False):
            index += 1
            continue
        start = index
        index += 1
        while index < total:
            if not lines[index].strip():
                next_line = _next_non_blank_line_index(lines, index)
                if next_line is not None and _is_mce_status_only_starter(lines[next_line]):
                    break
            elif _is_mce_detail_line(lines[index]) and not _is_mce_incident_line(lines[index]):
                break
            elif _is_mce_block_starter(lines[index], in_block=True):
                break
            elif not _is_mce_incident_line(lines[index]) and not _has_mce_incident_line_ahead(
                lines, index
            ):
                break
            index += 1
        blocks.append((start, index))
    return blocks


def hardware_error_block_line_indices(content: str) -> frozenset[int]:
    """Return [Hardware Error]: line indices that belong to an MCE incident block."""
    lines = content.splitlines()
    suppressed: set[int] = set()
    for start, end in iter_hardware_error_block_ranges(lines):
        suppressed.update(_mce_detail_line_indices_in_range(lines, start, end))
    return frozenset(suppressed)


def mce_block_all_line_indices(content: str) -> frozenset[int]:
    """Return every line index that belongs to an MCE incident block."""
    lines = content.splitlines()
    suppressed: set[int] = set()
    for start, end in iter_hardware_error_block_ranges(lines):
        suppressed.update(range(start, end))
    return frozenset(suppressed)


def ignored_mce_block_line_indices(content: str, ignore_banks: FrozenSet[int]) -> frozenset[int]:
    """Return [Hardware Error]: line indices for MCE blocks containing any ignored MCA bank."""
    if not ignore_banks:
        return frozenset()
    lines = content.splitlines()
    suppressed: set[int] = set()
    for start, end in iter_hardware_error_block_ranges(lines):
        block_banks: set[int] = set()
        for line in lines[start:end]:
            block_banks.update(extract_mce_banks_from_text(line))
        if block_banks & ignore_banks:
            suppressed.update(_mce_detail_line_indices_in_range(lines, start, end))
    return frozenset(suppressed)


def parse_correctable_mce_counts(
    content: str,
    ignore_banks: Optional[FrozenSet[int]] = None,
) -> dict[str, int]:
    """Count correctable MCE hardware errors per CPU from MCn_STATUS[|CE|] rows."""
    counts: dict[str, int] = {}
    ignored = ignore_banks or frozenset()
    ignored_block_lines = ignored_mce_block_line_indices(content, ignored)

    for line_no, line in enumerate(content.splitlines()):
        if line_no in ignored_block_lines:
            continue

        status_match = _MCE_CE_STATUS_RE.search(line)
        if status_match:
            part = (
                _normalize_cpu_label(status_match.group("cpu"))
                if status_match.group("cpu")
                else "unknown"
            )
            _add_count(counts, part, 1)

    return counts


def parse_uncorrectable_mce_counts(
    content: str,
    ignore_banks: Optional[FrozenSet[int]] = None,
) -> dict[str, int]:
    """Count uncorrectable MCE hardware errors per CPU from MCn_STATUS[|UC|] rows."""
    counts: dict[str, int] = {}
    ignored = ignore_banks or frozenset()
    ignored_block_lines = ignored_mce_block_line_indices(content, ignored)

    for line_no, line in enumerate(content.splitlines()):
        if line_no in ignored_block_lines:
            continue

        status_match = _MCE_UC_STATUS_RE.search(line)
        if status_match:
            part = (
                _normalize_cpu_label(status_match.group("cpu"))
                if status_match.group("cpu")
                else "unknown"
            )
            _add_count(counts, part, 1)

    return counts
