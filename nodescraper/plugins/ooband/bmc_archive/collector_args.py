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
from typing import Optional

from pydantic import Field, field_validator, model_validator

from nodescraper.models import CollectorArgs


class PathSpec(CollectorArgs):
    """One named BMC directory path to archive."""

    name: str = Field(description="Stable name for this archive, used in output filenames.")
    path: str = Field(description="Absolute BMC path to tar.")
    sudo: Optional[bool] = Field(
        default=None,
        description="Run tar with sudo. When omitted, uses collection_args.sudo.",
    )
    timeout: Optional[int] = Field(
        default=None,
        ge=1,
        description="Tar command timeout in seconds. When omitted, uses collection_args.timeout.",
    )
    skip_if_missing: Optional[bool] = Field(
        default=None,
        description="Skip this path when it does not exist on the BMC. When omitted, uses collection_args.skip_if_missing.",
    )
    ignore_failed_read: Optional[bool] = Field(
        default=None,
        description=(
            "Pass --ignore-failed-read to tar so unreadable files do not abort the archive. "
            "When omitted, uses collection_args.ignore_failed_read."
        ),
    )

    @field_validator("name", "path", mode="before")
    @classmethod
    def _strip_required_text(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @model_validator(mode="after")
    def _validate_required_fields(self) -> "PathSpec":
        if not self.name:
            raise ValueError("name must not be empty")
        if not self.path:
            raise ValueError("path must not be empty")
        if not self.path.startswith("/"):
            raise ValueError("path must be an absolute BMC path")
        return self


class BmcArchiveCollectorArgs(CollectorArgs):
    paths: list[PathSpec] = Field(
        default_factory=list,
        description=(
            "Named BMC paths to archive with tar czf -. "
            "Configure in plugin config under plugins.OobBmcArchivePlugin.collection_args.paths."
        ),
    )
    sudo: bool = Field(
        default=False,
        description="Default sudo setting for paths that do not specify sudo.",
    )
    timeout: int = Field(
        default=600,
        ge=1,
        description="Default per-path tar timeout in seconds.",
    )
    skip_if_missing: bool = Field(
        default=False,
        description="Skip paths that do not exist on the BMC instead of failing collection.",
    )
    ignore_failed_read: bool = Field(
        default=True,
        description=(
            "When true, pass GNU tar's --ignore-failed-read when the remote tar supports it."
        ),
    )

    @model_validator(mode="after")
    def _validate_unique_path_names(self) -> "BmcArchiveCollectorArgs":
        seen: set[str] = set()
        duplicates: set[str] = set()
        for path_spec in self.paths:
            if path_spec.name in seen:
                duplicates.add(path_spec.name)
            seen.add(path_spec.name)
        if duplicates:
            raise ValueError(f"Duplicate path name(s): {sorted(duplicates)}")
        return self
