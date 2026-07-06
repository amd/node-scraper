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
import pytest

from nodescraper.base.match_ignore import (
    extract_mce_bank_from_line,
    parse_ignore_match_rules,
    parse_mce_bank_spec,
    should_ignore_match,
)


def test_parse_mce_bank_spec_single_multiple_and_range():
    assert parse_mce_bank_spec([21]) == frozenset({21})
    assert parse_mce_bank_spec([21, 22, "60-63"]) == frozenset({21, 22, 60, 61, 62, 63})


def test_parse_ignore_match_rules_collects_mce_banks():
    rules, ignored_banks = parse_ignore_match_rules(
        [
            {"mce_banks": [21, 22]},
            {"mce_banks": ["60-63"]},
        ]
    )

    assert len(rules) == 2
    assert ignored_banks == frozenset({21, 22, 60, 61, 62, 63})


def test_parse_ignore_match_rules_invalid_rule():
    with pytest.raises(ValueError):
        parse_ignore_match_rules([{"message": "MCE Corrected Error"}])


def test_should_ignore_match_line_regex():
    rules, _ = parse_ignore_match_rules([{"line_regex": r"GPU reset begin"}])
    assert should_ignore_match(
        line="kern: GPU reset begin on device 0",
        match_text="GPU reset begin on device 0",
        error_regex_message="GPU Reset",
        rules=rules,
    )
    assert not should_ignore_match(
        line="kern: GPU reset succeeded",
        match_text="GPU reset succeeded",
        error_regex_message="GPU Reset",
        rules=rules,
    )


def test_should_ignore_match_message_scoped_mce_banks():
    rules, _ = parse_ignore_match_rules([{"message": "MCE Corrected Error", "mce_banks": [21]}])
    line = "[Hardware Error]: CPU0 MC21_STATUS[0x0|CE|]: 0x1"

    assert should_ignore_match(
        line=line,
        match_text=line,
        error_regex_message="MCE Corrected Error",
        rules=rules,
    )
    assert not should_ignore_match(
        line=line,
        match_text=line,
        error_regex_message="RAS Correctable Error",
        rules=rules,
    )


def test_should_ignore_match_mce_banks_only_when_all_banks_ignored():
    rules, _ = parse_ignore_match_rules([{"mce_banks": [1, 2]}])
    multiline_match = (
        "[Hardware Error]: CPU0 MC1_STATUS[0x0|CE|]: 0x1\n"
        "[Hardware Error]: CPU0 MC5_STATUS[0x0|CE|]: 0x3"
    )

    assert (
        should_ignore_match(
            line="kern: [Hardware Error]: CPU0 MC1_STATUS[0x0|CE|]: 0x1",
            match_text=multiline_match,
            error_regex_message="MCE Corrected Error",
            rules=rules,
        )
        is False
    )


def test_extract_mce_bank_from_line():
    line = "[Hardware Error]: Machine Check: CPU0 MC21_STATUS[0xcafe|CE|Misc]: 0x0"
    assert extract_mce_bank_from_line(line) == 21
