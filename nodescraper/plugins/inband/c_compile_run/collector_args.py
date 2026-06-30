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
from pathlib import PurePosixPath
from typing import Optional, Union

from pydantic import Field, field_validator, model_validator

from nodescraper.models import CollectorArgs


class CCompileRunCollectorArgs(CollectorArgs):
    """Arguments for compiling and running a C source file on the target host."""

    source_path: str = Field(
        description="Absolute or relative path to the .c source file on the target.",
    )
    gcc_extra_args: list[str] = Field(
        default_factory=list,
        description=(
            "Extra gcc flags inserted before -o (e.g. ['-Wall', '-O2', '-std=c99']). "
            "Each list entry is one shell argument."
        ),
    )
    output_path: Optional[str] = Field(
        default=None,
        description=(
            "Output binary path on the target. When omitted, uses the source path "
            "with the .c suffix removed."
        ),
    )
    run_args: list[str] = Field(
        default_factory=list,
        description="Arguments passed to the compiled binary when executed.",
    )
    gcc: str = Field(
        default="gcc",
        description="Compiler executable name or path on the target.",
    )
    work_dir: Optional[str] = Field(
        default=None,
        description="Optional working directory on the target (cd before compile and run).",
    )
    compile_sudo: bool = Field(
        default=False,
        description="Run the gcc compile command with sudo on the target.",
    )
    run_sudo: bool = Field(
        default=False,
        description="Run the compiled binary with sudo on the target.",
    )
    compile_timeout: int = Field(
        default=300,
        ge=1,
        description="Timeout in seconds for the gcc compile step.",
    )
    run_timeout: int = Field(
        default=300,
        ge=1,
        description="Timeout in seconds for executing the compiled binary.",
    )
    include_stdout: bool = Field(
        default=True,
        description="Store stdout from compile and run in the collected data model.",
    )

    @field_validator("source_path", "output_path", "work_dir", "gcc", mode="before")
    @classmethod
    def _strip_optional_text(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("gcc_extra_args", "run_args", mode="before")
    @classmethod
    def _coerce_arg_list(cls, value: Optional[Union[str, list[str]]]) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            if not value.strip():
                return []
            return [value.strip()]
        return [str(item).strip() for item in value if str(item).strip()]

    @model_validator(mode="after")
    def _validate_paths(self) -> "CCompileRunCollectorArgs":
        if not self.source_path:
            raise ValueError("source_path must not be empty")
        if "\n" in self.source_path or "\r" in self.source_path:
            raise ValueError("source_path must not contain newlines")
        suffix = PurePosixPath(self.source_path).suffix.lower()
        if suffix != ".c":
            raise ValueError("source_path must end with .c")
        if self.output_path and ("\n" in self.output_path or "\r" in self.output_path):
            raise ValueError("output_path must not contain newlines")
        if self.work_dir and ("\n" in self.work_dir or "\r" in self.work_dir):
            raise ValueError("work_dir must not contain newlines")
        if not self.gcc:
            raise ValueError("gcc must not be empty")
        return self

    def resolved_output_path(self) -> str:
        """Return the binary path used for -o and execution."""
        if self.output_path:
            return self.output_path
        return str(PurePosixPath(self.source_path).with_suffix(""))
