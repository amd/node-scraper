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
from typing import FrozenSet, Optional

from nodescraper.base.match_ignore import extract_mce_bank_from_line

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

    for line in content.splitlines():
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
            bank = extract_mce_bank_from_line(line)
            if bank is not None and bank in ignored:
                continue
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

    for line in content.splitlines():
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
            bank = extract_mce_bank_from_line(line)
            if bank is not None and bank in ignored:
                continue
            part = (
                _normalize_cpu_label(status_match.group("cpu"))
                if status_match.group("cpu")
                else "unknown"
            )
            _add_count(counts, part, 1)

    return counts
