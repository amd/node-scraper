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
from typing import Literal, Optional, Union

from pydantic import BaseModel, Field, field_validator, model_validator

from nodescraper.models import AnalyzerArgs

CompareOp = Literal["==", "!=", ">", ">=", "<", "<="]
MatchMode = Literal["full", "any_line", "all_lines"]
ValueType = Literal["int", "float", "str"]


class CommandCheck(BaseModel):
    """Validation rule for one collected command result, matched by collector command name."""

    model_config = {"extra": "forbid"}

    name: str = Field(
        description="Name of the collected command to validate (must match collection_args.commands[].name).",
    )
    allow_failure: bool = Field(
        default=False,
        description="When True, a collection failure for this command does not fail the check.",
    )
    expected_exit_code: Optional[int] = Field(
        default=None,
        description="Expected exit code from collection. Defaults to 0 when other content checks are set.",
    )
    must_contain: Optional[Union[str, list[str]]] = Field(
        default=None,
        description="Stdout must contain this text or all texts in the list.",
    )
    must_not_contain: Optional[Union[str, list[str]]] = Field(
        default=None,
        description="Stdout must not contain this text or any texts in the list.",
    )
    expected: Optional[str] = Field(
        default=None,
        description="Exact stdout match after strip.",
    )
    expected_in: Optional[list[str]] = Field(
        default=None,
        description="Stripped stdout must be one of these values.",
    )
    expected_regex: Optional[str] = Field(
        default=None,
        description="Stdout must match this regex.",
    )
    forbidden_regex: Optional[str] = Field(
        default=None,
        description="Stdout must not match this regex.",
    )
    ignore_case: bool = Field(
        default=False,
        description="Case-insensitive matching for substring and regex checks.",
    )
    match_mode: MatchMode = Field(
        default="full",
        description="How to apply regex checks: full output, any line, or all non-empty lines.",
    )
    min_lines: Optional[int] = Field(default=None, ge=0)
    max_lines: Optional[int] = Field(default=None, ge=0)
    exact_lines: Optional[int] = Field(default=None, ge=0)
    value_type: ValueType = Field(
        default="int",
        description="Type used when parsing stdout for expected_value checks.",
    )
    compare_op: CompareOp = Field(
        default="==",
        description="Comparison operator for expected_value checks.",
    )
    expected_value: Optional[Union[int, float, str]] = Field(
        default=None,
        description="Value to compare against parsed stdout.",
    )
    capture_regex: Optional[str] = Field(
        default=None,
        description="Optional regex with a capture group used before expected_value comparison.",
    )

    @field_validator("name", mode="before")
    @classmethod
    def _strip_name(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @model_validator(mode="after")
    def _validate_name(self) -> "CommandCheck":
        if not self.name:
            raise ValueError("name must not be empty")
        return self


class GenericAnalyzerArgs(AnalyzerArgs):
    checks: list[CommandCheck] = Field(
        default_factory=list,
        description="Per-command validation rules keyed by collected command name.",
    )

    @model_validator(mode="after")
    def _validate_unique_check_names(self) -> "GenericAnalyzerArgs":
        seen: set[str] = set()
        duplicates: set[str] = set()
        for check in self.checks:
            if check.name in seen:
                duplicates.add(check.name)
            seen.add(check.name)
        if duplicates:
            raise ValueError(f"Duplicate check name(s): {sorted(duplicates)}")
        return self
