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
from dataclasses import dataclass
from typing import Optional, Sequence, Union

_MCE_BANK_RE = re.compile(r"\bMC(?P<bank>\d+)_STATUS\b", re.IGNORECASE)

MceBankSpec = Union[int, str]
IgnoreMatchRuleSpec = dict[str, object]


@dataclass(frozen=True)
class ParsedIgnoreMatchRule:
    line_regex: Optional[re.Pattern[str]] = None
    match_regex: Optional[re.Pattern[str]] = None
    messages: Optional[frozenset[str]] = None
    mce_banks: Optional[frozenset[int]] = None


def parse_mce_bank_spec(spec: Sequence[MceBankSpec]) -> frozenset[int]:
    """Expand MCA bank ids and inclusive ranges into a set of bank numbers.

    Args:
        spec: Bank ids, bank ranges like "60-63", or an empty sequence.

    Returns:
        frozenset[int]: MCA bank numbers.
    """
    banks: set[int] = set()
    for entry in spec:
        if isinstance(entry, int):
            if entry < 0:
                raise ValueError(f"Invalid MCE bank number: {entry}")
            banks.add(entry)
            continue

        token = str(entry).strip()
        if not token:
            raise ValueError("Empty MCE bank entry")

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


def extract_mce_banks_from_text(text: str) -> frozenset[int]:
    """Return all MCA bank numbers referenced in text.

    Args:
        text: Log line or regex match text.

    Returns:
        frozenset[int]: MCA bank numbers found in text.
    """
    return frozenset(int(match.group("bank")) for match in _MCE_BANK_RE.finditer(text))


def parse_ignore_match_rules(
    spec: Optional[Sequence[IgnoreMatchRuleSpec]],
) -> tuple[list[ParsedIgnoreMatchRule], frozenset[int]]:
    """Parse ignore_match_rules config into compiled skip rules and ignored MCA banks.

    Args:
        spec: Rule dicts using line_regex, match_regex, message, and/or mce_banks.

    Returns:
        tuple[list[ParsedIgnoreMatchRule], frozenset[int]]: Parsed rules and all ignored MCA banks.
    """
    if not spec:
        return [], frozenset()

    parsed_rules: list[ParsedIgnoreMatchRule] = []
    ignored_mce_banks: set[int] = set()

    for index, raw_rule in enumerate(spec):
        if not isinstance(raw_rule, dict):
            raise ValueError(f"ignore_match_rules[{index}] must be a dict")

        line_regex = raw_rule.get("line_regex")
        match_regex = raw_rule.get("match_regex")
        message = raw_rule.get("message")
        mce_banks = raw_rule.get("mce_banks")

        if line_regex is None and match_regex is None and mce_banks is None:
            raise ValueError(
                f"ignore_match_rules[{index}] must specify at least one of "
                "line_regex, match_regex, or mce_banks"
            )

        messages: Optional[frozenset[str]] = None
        if message is not None:
            if isinstance(message, str):
                messages = frozenset({message})
            elif isinstance(message, list) and all(isinstance(item, str) for item in message):
                messages = frozenset(message)
            else:
                raise ValueError(
                    f"ignore_match_rules[{index}].message must be a string or list of strings"
                )

        parsed_mce_banks: Optional[frozenset[int]] = None
        if mce_banks is not None:
            if not isinstance(mce_banks, list):
                raise ValueError(f"ignore_match_rules[{index}].mce_banks must be a list")
            parsed_mce_banks = parse_mce_bank_spec(mce_banks)
            ignored_mce_banks.update(parsed_mce_banks)

        parsed_rules.append(
            ParsedIgnoreMatchRule(
                line_regex=re.compile(str(line_regex)) if line_regex is not None else None,
                match_regex=re.compile(str(match_regex)) if match_regex is not None else None,
                messages=messages,
                mce_banks=parsed_mce_banks,
            )
        )

    return parsed_rules, frozenset(ignored_mce_banks)


def should_ignore_match(
    *,
    line: str,
    match_text: str,
    error_regex_message: str,
    rules: Sequence[ParsedIgnoreMatchRule],
) -> bool:
    """Return True when any ignore rule matches the current regex hit.

    Args:
        line: Full log line containing the match.
        match_text: Regex match text.
        error_regex_message: ErrorRegex.message for the pattern that matched.
        rules: Parsed ignore rules; first matching rule wins.

    Returns:
        bool: True when the match should be skipped.
    """
    for rule in rules:
        if rule.messages is not None and error_regex_message not in rule.messages:
            continue

        if rule.mce_banks is not None:
            banks = extract_mce_banks_from_text(match_text)
            if not banks:
                line_bank = extract_mce_bank_from_line(line)
                banks = frozenset({line_bank}) if line_bank is not None else frozenset()
            if not banks or not banks.issubset(rule.mce_banks):
                continue

        if rule.line_regex is not None and rule.line_regex.search(line) is None:
            continue

        if rule.match_regex is not None and rule.match_regex.search(match_text) is None:
            continue

        return True

    return False
