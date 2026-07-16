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
from nodescraper.plugins.inband.dmesg.mce_utils import (
    hardware_error_block_line_indices,
    ignored_mce_block_line_indices,
    iter_hardware_error_block_ranges,
    parse_correctable_mce_counts,
    parse_uncorrectable_mce_counts,
    trim_mce_status_match_content,
)


def test_parse_correctable_mce_counts_cpu_summary_and_status():
    content = (
        "kern  :warn  : 2038-01-19T00:00:00,000000+00:00 "
        "mce: 3 correctable hardware errors detected in total in mc0 block on CPU1\n"
        "kern  :warn  : 2038-01-19T00:00:01,000000+00:00 "
        "[Hardware Error]: CPU0 MC2_STATUS[0x0|CE|]: 0xabc\n"
    )

    counts = parse_correctable_mce_counts(content)

    assert counts == {"CPU1/mc0": 3, "CPU0": 1}


def test_parse_correctable_mce_counts_gpu_summary():
    content = (
        "kern  :err   : 2038-01-19T00:00:00,000000+00:00 "
        "amdgpu 0000:de:ad.0: amdgpu: socket: 4, die: 0 "
        "3 correctable hardware errors detected in total in gfx block\n"
    )

    counts = parse_correctable_mce_counts(content)

    assert counts == {"GPU0/gfx": 3}


def test_parse_uncorrectable_mce_counts():
    content = (
        "kern  :err   : 2038-01-19T00:00:01,000000+00:00 "
        "[Hardware Error]: Machine Check: CPU1 MC1_STATUS[0xfeed|UC|AddrV]: 0x0\n"
        "amdgpu 0000:de:ad.0: amdgpu: socket: 0 2 uncorrectable hardware errors detected in gfx block\n"
    )

    counts = parse_uncorrectable_mce_counts(content)

    assert counts == {"CPU1": 1, "GPU0/gfx": 2}


def test_parse_correctable_mce_counts_skips_ignored_banks():
    content = (
        "[Hardware Error]: CPU0 MC1_STATUS[0x0|CE|]: 0x1\n"
        "[Hardware Error]: CPU0 MC2_STATUS[0x0|CE|]: 0x2\n"
        "[Hardware Error]: CPU0 MC5_STATUS[0x0|CE|]: 0x3\n"
    )

    counts = parse_correctable_mce_counts(content, ignore_banks=frozenset({1, 2}))

    assert counts == {}


def test_parse_correctable_mce_counts_skips_ignored_banks_in_separate_block():
    content = (
        "[Hardware Error]: CPU0 MC1_STATUS[0x0|CE|]: 0x1\n"
        "[Hardware Error]: CPU0 MC2_STATUS[0x0|CE|]: 0x2\n"
        "\n"
        "[Hardware Error]: CPU0 MC5_STATUS[0x0|CE|]: 0x3\n"
    )

    counts = parse_correctable_mce_counts(content, ignore_banks=frozenset({1, 2}))

    assert counts == {"CPU0": 1}


def test_hardware_error_block_line_indices():
    content = (
        "kern  :emerg : ts [Hardware Error]: Corrected error, no action required.\n"
        "kern  :emerg : ts [Hardware Error]: CPU:12 MC60_STATUS[Over|CE|MiscV]: 0x1\n"
        "kern  :emerg : ts [Hardware Error]: PPIN: 0xabc\n"
        "kern  :info  : ts unrelated line\n"
    )

    assert hardware_error_block_line_indices(content) == frozenset({0, 1, 2})


def test_hardware_error_block_splits_info_preamble_from_emerg_details():
    content = (
        "kern  :info  : 2038-01-19T00:00:00,000000+00:00 "
        "mce: [Hardware Error]: Machine check events logged\n"
        "kern  :emerg : 2038-01-19T00:00:01,000000+00:00 "
        "[Hardware Error]: Corrected error, no action required.\n"
        "kern  :emerg : 2038-01-19T00:00:02,000000+00:00 "
        "[Hardware Error]: CPU:12 (00:00:0) MC60_STATUS[Over|CE|MiscV|-|-|-|SyndV|UECC|-|-|-]: 0xaaa\n"
        "kern  :emerg : 2038-01-19T00:00:04,000000+00:00 [Hardware Error]: PPIN: 0xbbbbbbbbbbbbbbbb\n"
        "kern  :emerg : 2038-01-19T00:00:05,000000+00:00 "
        "[Hardware Error]: IPID: 0x0000000000000001, Syndrome: 0x0000000000000001\n"
        "kern  :emerg : 2038-01-19T00:00:06,000000+00:00 "
        "[Hardware Error]: cache level: L3/GEN, mem/io: IO, mem-tx: GEN, part-proc: SRC (no timeout)\n"
    )
    lines = content.splitlines()

    assert iter_hardware_error_block_ranges(lines) == [(0, 1), (1, 6)]
    assert hardware_error_block_line_indices(content) == frozenset({0, 1, 2, 3, 4, 5})
    assert ignored_mce_block_line_indices(content, frozenset({60})) == frozenset({1, 2, 3, 4, 5})


def test_hardware_error_block_includes_interleaved_non_mce_lines():
    content = (
        "kern  :emerg : ts [Hardware Error]: Corrected error, no action required.\n"
        "kern  :emerg : ts [Hardware Error]: CPU:12 MC60_STATUS[Over|CE|MiscV]: 0x1\n"
        "kern  :emerg : ts amdgpu 0000:de:ad.0: amdgpu: unrelated reset notice\n"
        "kern  :emerg : ts [Hardware Error]: PPIN: 0xabc\n"
        "kern  :emerg : ts [Hardware Error]: cache level: L3/GEN\n"
    )

    assert hardware_error_block_line_indices(content) == frozenset({0, 1, 3, 4})
    assert ignored_mce_block_line_indices(content, frozenset({60})) == frozenset({0, 1, 3, 4})


def test_ignored_mce_block_line_indices():
    content = (
        "kern  :emerg : ts [Hardware Error]: Corrected error, no action required.\n"
        "kern  :emerg : ts [Hardware Error]: CPU:12 MC60_STATUS[Over|CE|MiscV]: 0x1\n"
        "kern  :emerg : ts [Hardware Error]: PPIN: 0xabc\n"
        "\n"
        "kern  :emerg : ts [Hardware Error]: Corrected error, no action required.\n"
        "kern  :err   : ts [Hardware Error]: CPU0 MC5_STATUS[0x0|CE|]: 0x3\n"
    )

    ignored = ignored_mce_block_line_indices(content, frozenset({60}))

    assert ignored == frozenset({0, 1, 2})
    assert iter_hardware_error_block_ranges(content.splitlines()) == [(0, 4), (4, 6)]


def test_mce_block_includes_blank_line_and_warn_interleave():
    """Dummy excerpt: warn/workqueue noise and blank lines inside one MCE block."""
    content = (
        "kern  :info  : 2038-01-19T00:00:00,000000+00:00 "
        "mce: [Hardware Error]: Machine check events logged\n"
        "kern  :emerg : 2038-01-19T00:00:01,000000+00:00 "
        "[Hardware Error]: Corrected error, no action required.\n"
        "kern  :emerg : 2038-01-19T00:00:02,000000+00:00 "
        "[Hardware Error]: CPU:12 (00:00:0) MC60_STATUS[Over|CE|MiscV|-|-|-|SyndV|UECC|-|-|-]: 0xaaa\n"
        "kern  :warn  : 2038-01-19T00:00:03,000000+00:00 "
        "workqueue: dummy_mce_worker hogged CPU for >10000us 5 times, consider switching to WQ_UNBOUND\n"
        "kern  :emerg : 2038-01-19T00:00:04,000000+00:00 [Hardware Error]: PPIN: 0xbbbbbbbbbbbbbbbb\n"
        "kern  :emerg : 2038-01-19T00:00:05,000000+00:00 "
        "[Hardware Error]: IPID: 0x0000000000000001, Syndrome: 0x0000000000000001\n"
        "\n"
        "kern  :emerg : 2038-01-19T00:00:06,000000+00:00 "
        "[Hardware Error]: cache level: L3/GEN, mem/io: IO, mem-tx: GEN, part-proc: SRC (no timeout)\n"
        "kern  :info  : 2038-01-19T00:00:07,000000+00:00 "
        "mce: [Hardware Error]: Machine check events logged\n"
        "kern  :emerg : 2038-01-19T00:00:08,000000+00:00 "
        "[Hardware Error]: Corrected error, no action required.\n"
        "kern  :emerg : 2038-01-19T00:00:09,000000+00:00 "
        "[Hardware Error]: CPU:24 (00:00:0) MC60_STATUS[Over|CE|MiscV|-|-|-|SyndV|UECC|-|-|-]: 0xbbb\n"
        "kern  :emerg : 2038-01-19T00:00:10,000000+00:00 [Hardware Error]: PPIN: 0xcccccccccccccccc\n"
    )
    lines = content.splitlines()

    assert iter_hardware_error_block_ranges(lines) == [(0, 1), (1, 8), (8, 9), (9, 12)]
    assert hardware_error_block_line_indices(content) == frozenset({0, 1, 2, 4, 5, 7, 8, 9, 10, 11})
    assert ignored_mce_block_line_indices(content, frozenset({60})) == frozenset(
        {1, 2, 4, 5, 7, 9, 10, 11}
    )
    assert 3 not in ignored_mce_block_line_indices(content, frozenset({60}))
    assert 6 not in ignored_mce_block_line_indices(content, frozenset({60}))


def test_trim_mce_status_match_content_keeps_status_row_only():
    multiline = (
        "[Hardware Error]: CPU:29 (00:00:0) MC49_STATUS[Over|CE|MiscV]: 0xbbb\n"
        "[Hardware Error]: Corrected error, no action required.\n"
        "[Hardware Error]: CPU:8 (00:00:0) MC60_STATUS[Over|CE|MiscV]: 0xccc\n"
    )

    trimmed = trim_mce_status_match_content(multiline)

    assert trimmed == ("[Hardware Error]: CPU:29 (00:00:0) MC49_STATUS[Over|CE|MiscV]: 0xbbb")
    assert "MC60_STATUS" not in trimmed
    assert "\n" not in trimmed


def test_parse_correctable_mce_counts_cpu_colon_status():
    content = (
        "kern  :err   : 2038-01-19T00:00:00,000000+00:00 "
        "[Hardware Error]: CPU:72 (00:00:0) MC60_STATUS[-|CE|Misc]: 0xabc\n"
    )

    counts = parse_correctable_mce_counts(content)

    assert counts == {"CPU72": 1}


def test_parse_correctable_mce_counts_both_cpu_formats():
    content = (
        "[Hardware Error]: CPU0 MC1_STATUS[0x0|CE|]: 0x1\n"
        "kern  :err   : 2038-01-19T00:00:00,000000+00:00 "
        "[Hardware Error]: CPU:72 (00:00:0) MC60_STATUS[-|CE|Misc]: 0xabc\n"
        "kern  :warn  : 2038-01-19T00:00:02,000000+00:00 "
        "mce: 2 correctable hardware errors detected in total in mc0 block on CPU:1\n"
    )

    counts = parse_correctable_mce_counts(content)

    assert counts == {"CPU0": 1, "CPU72": 1, "CPU1/mc0": 2}


def test_parse_uncorrectable_mce_counts_cpu_colon_status():
    content = (
        "kern  :err   : 2038-01-19T00:00:01,000000+00:00 "
        "[Hardware Error]: CPU:72 (00:00:0) MC60_STATUS[-|UC|Misc]: 0xdef\n"
    )

    counts = parse_uncorrectable_mce_counts(content)

    assert counts == {"CPU72": 1}
