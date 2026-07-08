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
from typing import FrozenSet, Optional, Sequence

from nodescraper.base.match_ignore import extract_mce_banks_from_text

_MCE_PRIMARY_START_RE = re.compile(
    r"\[Hardware Error\]:\s*(?:Corrected error|Uncorrected error|Machine check events logged)",
    re.IGNORECASE,
)
_MCE_STATUS_START_RE = re.compile(r"\bMC\d+_STATUS\[", re.IGNORECASE)
_MCE_DETAIL_LINE_RE = re.compile(r"\[Hardware Error\]:")

_CORRECTABLE_SUMMARY_RE = re.compile(
    r"(?P<count>\d+)\s+correctable hardware errors detected in total in (?P<block>\w+) block"
    r"(?:\s+on\s+(?P<cpu>CPU:?\d+))?",
    re.IGNORECASE,
)

_UNCORRECTABLE_SUMMARY_RE = re.compile(
    r"(?P<count>\d+)\s+uncorrectable hardware errors detected in (?P<block>\w+) block",
    re.IGNORECASE,
)

_GPU_CORRECTABLE_RE = re.compile(
    r"amdgpu\s+(?P<bdf>[\w:.]+):.*?(?P<count>\d+)\s+correctable hardware errors detected in total in "
    r"(?P<block>\w+) block",
    re.IGNORECASE,
)

_GPU_UNCORRECTABLE_RE = re.compile(
    r"amdgpu\s+(?P<bdf>[\w:.]+):.*?(?P<count>\d+)\s+uncorrectable hardware errors detected in "
    r"(?P<block>\w+) block",
    re.IGNORECASE,
)

_MCE_CE_STATUS_RE = re.compile(
    r"\[Hardware Error\]:.*?(?P<cpu>CPU:?\d+).*?MC\d+_STATUS\[[^\]]*\|CE\|[^\]]*\]",
    re.IGNORECASE,
)

_MCE_UC_STATUS_RE = re.compile(
    r"\[Hardware Error\]:.*?(?P<cpu>CPU:?\d+).*?MC\d+_STATUS\[[^\]]*\|UC\|[^\]]*\]",
    re.IGNORECASE,
)


def _normalize_cpu_label(cpu: str) -> str:
    return cpu.replace(":", "")


def _add_count(counts: dict[str, int], part: str, amount: int) -> None:
    counts[part] = counts.get(part, 0) + amount


def _part_label(
    *,
    cpu: Optional[str] = None,
    block: Optional[str] = None,
    bdf: Optional[str] = None,
    gpu_index: Optional[int] = None,
) -> str:
    if bdf is not None:
        block_suffix = f"/{block}" if block else ""
        if gpu_index is not None:
            return f"GPU{gpu_index}{block_suffix}"
        return f"GPU {bdf}{block_suffix}"
    if cpu and block:
        return f"{cpu}/{block}"
    if cpu:
        return cpu
    if block:
        return block
    return "unknown"


def _gpu_index_for_bdf(bdf: str, bdf_order: list[str]) -> int:
    if bdf not in bdf_order:
        bdf_order.append(bdf)
    return bdf_order.index(bdf)


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


def _has_mce_detail_line_ahead(lines: Sequence[str], start_index: int) -> bool:
    """Return True when another [Hardware Error]: line appears before the next incident."""
    for idx in range(start_index + 1, len(lines)):
        line = lines[idx]
        if not line.strip():
            continue
        if _is_mce_primary_starter(line):
            return False
        if _is_mce_status_only_starter(line):
            return False
        if _is_mce_detail_line(line):
            return True
    return False


def iter_hardware_error_block_ranges(lines: Sequence[str]) -> list[tuple[int, int]]:
    """Return (start, end) line index ranges for MCE incident blocks.

    A block begins at a primary MCE header (Corrected/Uncorrected/Machine check logged)
    or at the first MCn_STATUS line when not already inside a block. The block then
    includes subsequent lines until the next primary header, a blank line before a bare
    MCn_STATUS starter, trailing non-MCE lines with no further [Hardware Error]: detail,
    or EOF. Blank lines, warn/err noise, and other non-MCE dmesg lines between detail
    entries belong to the same block.
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
            elif _is_mce_block_starter(lines[index], in_block=True):
                break
            elif not _is_mce_detail_line(lines[index]) and not _has_mce_detail_line_ahead(
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
    """Count correctable MCE / RAS hardware errors per component from dmesg text.

    Handles summary lines (for example ``mce: 3 correctable ... on CPU1``),
    amdgpu block summaries, and per-event ``MCn_STATUS[|CE|]`` hardware error lines.
    """
    counts: dict[str, int] = {}
    gpu_bdf_order: list[str] = []
    ignored = ignore_banks or frozenset()
    ignored_block_lines = ignored_mce_block_line_indices(content, ignored)

    for line_no, line in enumerate(content.splitlines()):
        if line_no in ignored_block_lines:
            continue
        gpu_match = _GPU_CORRECTABLE_RE.search(line)
        if gpu_match:
            bdf = gpu_match.group("bdf")
            part = _part_label(
                bdf=bdf,
                block=gpu_match.group("block"),
                gpu_index=_gpu_index_for_bdf(bdf, gpu_bdf_order),
            )
            _add_count(counts, part, int(gpu_match.group("count")))
            continue

        summary_match = _CORRECTABLE_SUMMARY_RE.search(line)
        if summary_match:
            cpu = summary_match.group("cpu")
            part = _part_label(
                cpu=_normalize_cpu_label(cpu) if cpu else None,
                block=summary_match.group("block"),
            )
            _add_count(counts, part, int(summary_match.group("count")))
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
    """Count uncorrectable MCE / RAS hardware errors per component from dmesg text."""
    counts: dict[str, int] = {}
    gpu_bdf_order: list[str] = []
    ignored = ignore_banks or frozenset()
    ignored_block_lines = ignored_mce_block_line_indices(content, ignored)

    for line_no, line in enumerate(content.splitlines()):
        if line_no in ignored_block_lines:
            continue
        gpu_match = _GPU_UNCORRECTABLE_RE.search(line)
        if gpu_match:
            bdf = gpu_match.group("bdf")
            part = _part_label(
                bdf=bdf,
                block=gpu_match.group("block"),
                gpu_index=_gpu_index_for_bdf(bdf, gpu_bdf_order),
            )
            _add_count(counts, part, int(gpu_match.group("count")))
            continue

        summary_match = _UNCORRECTABLE_SUMMARY_RE.search(line)
        if summary_match:
            part = _part_label(block=summary_match.group("block"))
            _add_count(counts, part, int(summary_match.group("count")))
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
