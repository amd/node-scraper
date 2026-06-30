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
from typing import Optional, Union

from pydantic import Field, field_validator

from nodescraper.models import AnalyzerArgs


class CCompileRunAnalyzerArgs(AnalyzerArgs):
    """Validation rules for C compile/run results."""

    expected_compile_exit_code: int = Field(
        default=0,
        description="Expected exit code from gcc.",
    )
    expected_run_exit_code: int = Field(
        default=0,
        description="Expected exit code from executing the compiled binary.",
    )
    run_must_contain: Optional[Union[str, list[str]]] = Field(
        default=None,
        description="Run stdout must contain this text or all texts in the list.",
    )
    run_must_not_contain: Optional[Union[str, list[str]]] = Field(
        default=None,
        description="Run stdout must not contain this text or any texts in the list.",
    )

    @field_validator("run_must_contain", "run_must_not_contain", mode="before")
    @classmethod
    def _coerce_optional_text(cls, value: Optional[Union[str, list[str]]]) -> object:
        if value is None:
            return None
        if isinstance(value, str):
            return value
        return [str(item) for item in value]
