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
    parse_correctable_mce_counts,
    parse_uncorrectable_mce_counts,
)


def test_parse_correctable_mce_counts_cpu_summary_and_status():
    content = (
        "kern  :warn  : 2024-06-11T14:30:00,123456+00:00 "
        "mce: 3 correctable hardware errors detected in total in mc0 block on CPU1\n"
        "kern  :warn  : 2024-06-11T14:30:02,222222+00:00 "
        "[Hardware Error]: CPU0 MC2_STATUS[0x0|CE|]: 0xabc\n"
    )

    counts = parse_correctable_mce_counts(content)

    assert counts == {"CPU1/mc0": 3, "CPU0": 1}


def test_parse_correctable_mce_counts_gpu_summary():
    content = (
        "kern  :err   : 2024-10-07T10:17:15,145363-04:00 "
        "amdgpu 0000:c1:00.0: amdgpu: socket: 4, die: 0 "
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

    assert counts == {"CPU0": 1}


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
        "kern  :warn  : 2024-06-11T14:30:00,123456+00:00 "
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
