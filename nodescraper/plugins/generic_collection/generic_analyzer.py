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
import operator
import re
from typing import Callable, Optional, Union

from nodescraper.enums import EventCategory, EventPriority, ExecutionStatus
from nodescraper.interfaces import DataAnalyzer
from nodescraper.models import TaskResult

from .analyzer_args import CommandCheck, CompareOp, GenericAnalyzerArgs
from .generic_collection_data import CommandCollectionResult, GenericCollectionDataModel

_COMPARE_OPS: dict[CompareOp, Callable[[Union[int, float, str], Union[int, float, str]], bool]] = {
    "==": operator.eq,
    "!=": operator.ne,
    ">": operator.gt,
    ">=": operator.ge,
    "<": operator.lt,
    "<=": operator.le,
}


def _as_list(value: Union[str, list[str]]) -> list[str]:
    if isinstance(value, str):
        return [value]
    return list(value)


def _non_empty_lines(stdout: str) -> list[str]:
    return [line for line in stdout.splitlines() if line.strip()]


def _needs_stdout(check: CommandCheck) -> bool:
    return any(
        [
            check.must_contain is not None,
            check.must_not_contain is not None,
            check.expected is not None,
            check.expected_in is not None,
            check.expected_regex is not None,
            check.forbidden_regex is not None,
            check.min_lines is not None,
            check.max_lines is not None,
            check.exact_lines is not None,
            check.expected_value is not None,
        ]
    )


def _check_label(check: CommandCheck) -> str:
    return check.name


def _find_result(
    data: GenericCollectionDataModel, check: CommandCheck
) -> Optional[CommandCollectionResult]:
    for result in data.results:
        if result.name == check.name:
            return result
    return None


def _regex_flags(ignore_case: bool) -> int:
    return re.IGNORECASE if ignore_case else 0


def _regex_matches(pattern: str, text: str, mode: str, ignore_case: bool) -> bool:
    flags = _regex_flags(ignore_case)
    compiled = re.compile(pattern, flags)
    if mode == "full":
        return compiled.search(text) is not None
    lines = _non_empty_lines(text)
    if not lines:
        return False
    if mode == "any_line":
        return any(compiled.search(line) for line in lines)
    return all(compiled.search(line) for line in lines)


def _contains(text: str, needle: str, ignore_case: bool) -> bool:
    if ignore_case:
        return needle.lower() in text.lower()
    return needle in text


def _parse_value(raw: str, value_type: str, capture_regex: Optional[str]) -> Union[int, float, str]:
    value = raw.strip()
    if capture_regex:
        match = re.search(capture_regex, value)
        if not match:
            raise ValueError(f"capture_regex {capture_regex!r} did not match stdout")
        value = match.group(1) if match.groups() else match.group(0)
        value = value.strip()
    if value_type == "int":
        return int(value)
    if value_type == "float":
        return float(value)
    return value


class GenericAnalyzer(DataAnalyzer[GenericCollectionDataModel, GenericAnalyzerArgs]):
    """Validate generic collection command results against analysis_args checks."""

    DATA_MODEL = GenericCollectionDataModel

    def analyze_data(
        self,
        data: GenericCollectionDataModel,
        args: Optional[GenericAnalyzerArgs] = None,
    ) -> TaskResult:
        if args is None:
            args = GenericAnalyzerArgs()

        if not data.results:
            self.result.message = "No command results to analyze"
            self.result.status = ExecutionStatus.NOT_RAN
            return self.result

        if not args.checks:
            success_count = sum(1 for result in data.results if result.success)
            self.result.message = (
                f"Generic analysis: {success_count}/{len(data.results)} commands collected"
            )
            self.result.status = ExecutionStatus.OK
            return self.result

        failures: list[str] = []
        failed_check_count = 0
        for check in args.checks:
            label = _check_label(check)
            result = _find_result(data, check)
            if result is None:
                failures.append(f"{label}: no matching collected command")
                failed_check_count += 1
                continue

            check_failures = self._evaluate_check(check, result)
            if check_failures:
                failed_check_count += 1
                failures.extend(f"{label}: {msg}" for msg in check_failures)
                self._log_event(
                    category=EventCategory.RUNTIME,
                    description=f"Check failed: {label}",
                    data={
                        "failures": check_failures,
                        "name": result.name,
                        "command": result.command,
                    },
                    priority=EventPriority.ERROR,
                    console_log=True,
                )
            else:
                self._log_event(
                    category=EventCategory.RUNTIME,
                    description=f"Check passed: {label}",
                    data={"name": result.name, "command": result.command},
                    priority=EventPriority.INFO,
                )

        if failed_check_count:
            passed = len(args.checks) - failed_check_count
            self.result.message = f"Generic analysis: {passed}/{len(args.checks)} checks passed"
            self.result.status = ExecutionStatus.ERROR
            return self.result

        self.result.message = (
            f"Generic analysis: {len(args.checks)}/{len(args.checks)} checks passed"
        )
        self.result.status = ExecutionStatus.OK
        return self.result

    def _evaluate_check(self, check: CommandCheck, result: CommandCollectionResult) -> list[str]:
        failures: list[str] = []

        if not result.success and not check.allow_failure:
            failures.append(f"command failed with exit code {result.exit_code}")
            if not _needs_stdout(check) and check.expected_exit_code is None:
                return failures

        expected_exit_code = check.expected_exit_code
        if expected_exit_code is None and _needs_stdout(check):
            expected_exit_code = 0
        if expected_exit_code is not None and result.exit_code != expected_exit_code:
            failures.append(f"expected exit code {expected_exit_code}, got {result.exit_code}")

        if not _needs_stdout(check):
            return failures

        if result.stdout is None:
            failures.append("stdout not collected; set include_stdout on the command")
            return failures

        stdout = result.stdout
        stripped = stdout.strip()

        for needle in _as_list(check.must_contain or []):
            if not _contains(stdout, needle, check.ignore_case):
                failures.append(f"must_contain {needle!r} not found")

        for needle in _as_list(check.must_not_contain or []):
            if _contains(stdout, needle, check.ignore_case):
                failures.append(f"must_not_contain {needle!r} found")

        if check.expected is not None and stripped != check.expected:
            failures.append(f"expected exact stdout {check.expected!r}, got {stripped!r}")

        if check.expected_in is not None and stripped not in check.expected_in:
            failures.append(f"stdout {stripped!r} not in expected_in")

        if check.expected_regex is not None and not _regex_matches(
            check.expected_regex, stdout, check.match_mode, check.ignore_case
        ):
            failures.append(f"expected_regex {check.expected_regex!r} did not match")

        if check.forbidden_regex is not None and _regex_matches(
            check.forbidden_regex, stdout, check.match_mode, check.ignore_case
        ):
            failures.append(f"forbidden_regex {check.forbidden_regex!r} matched")

        line_count = len(_non_empty_lines(stdout))
        if check.exact_lines is not None and line_count != check.exact_lines:
            failures.append(f"expected {check.exact_lines} non-empty lines, got {line_count}")
        if check.min_lines is not None and line_count < check.min_lines:
            failures.append(
                f"expected at least {check.min_lines} non-empty lines, got {line_count}"
            )
        if check.max_lines is not None and line_count > check.max_lines:
            failures.append(f"expected at most {check.max_lines} non-empty lines, got {line_count}")

        if check.expected_value is not None:
            try:
                parsed = _parse_value(stripped, check.value_type, check.capture_regex)
            except (TypeError, ValueError) as exc:
                failures.append(str(exc))
            else:
                compare = _COMPARE_OPS[check.compare_op]
                if not compare(parsed, check.expected_value):
                    failures.append(
                        f"expected parsed value {parsed!r} {check.compare_op} {check.expected_value!r}"
                    )

        return failures
