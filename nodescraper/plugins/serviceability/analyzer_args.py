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
from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import Field, field_validator, model_validator

from nodescraper.models import AnalyzerArgs

EngineBackend = Literal["python", "cli", "subprocess"]


class ServiceabilityAnalyzerArgs(AnalyzerArgs):
    """Analyzer args for serviceability plugins."""

    engine_backend: EngineBackend = Field(
        default="python",
        description=(
            "How to invoke the SE: 'python' (service_hub bindings), "
            "'cli' (external analyze subcommand), or 'subprocess' (--input/--output protocol)."
        ),
    )
    engine_python_module: str = Field(
        default="service_hub",
        description="Python package providing ServiceHub bindings (python backend).",
    )
    engine_executable: Optional[str] = Field(
        default=None,
        description="Path to the SE binary (cli or subprocess backends).",
    )
    engine_entry_point: Optional[str] = Field(
        default=None,
        description=(
            "Command for cli/subprocess backends: executable path or argv prefix on PATH. "
            "Required when engine_backend is 'cli' or 'subprocess'."
        ),
    )
    afid_sag_path: Optional[str] = Field(
        default=None,
        description="Path to AFID_SAG.json.",
    )
    engine_extra_args: List[str] = Field(
        default_factory=list,
        description="Extra CLI arguments (cli/subprocess backends).",
    )
    engine_timeout_seconds: int = Field(
        default=600,
        ge=1,
        le=86_400,
        description="Subprocess timeout (cli/subprocess backends).",
    )
    skip_engine: bool = Field(
        default=False,
        description="If True, only build afid_events without running the SE.",
    )

    @field_validator("engine_executable", "engine_entry_point", "afid_sag_path")
    @classmethod
    def _strip_optional_paths(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @model_validator(mode="after")
    def _require_engine_config_when_running(self) -> ServiceabilityAnalyzerArgs:
        if self.skip_engine:
            return self
        if not self.afid_sag_path:
            raise ValueError("afid_sag_path is required when running Service Hub.")
        if self.engine_backend == "python":
            return self
        has_exe = self.engine_executable is not None
        has_entry = self.engine_entry_point is not None
        if has_exe and has_entry:
            raise ValueError(
                "Provide only one of engine_executable or engine_entry_point "
                "for cli/subprocess backends."
            )
        if not has_exe and not has_entry:
            raise ValueError(
                "engine_executable or engine_entry_point is required when "
                "engine_backend is 'cli' or 'subprocess'."
            )
        return self
