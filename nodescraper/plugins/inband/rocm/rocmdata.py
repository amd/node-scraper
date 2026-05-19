###############################################################################
#
# MIT License
#
# Copyright (c) 2025 Advanced Micro Devices, Inc.
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
from typing import ClassVar, List, Optional

from pydantic import computed_field, field_validator

from nodescraper.models import DataModel

_ROCM_VERSION_RE = re.compile(r"^(\d+(?:\.\d+){0,3})(?:-(\d+)(?:-gfx\w+(?:;gfx\w+)*)?)?$")


class RocmDataModel(DataModel):
    ROCM_VERSION_FILENAME: ClassVar[str] = "version-rocm"

    rocm_version: str
    rocm_sub_versions: dict[str, str] = {}
    rocminfo: List[str] = []
    rocm_latest_versioned_path: str = ""
    rocm_all_paths: List[str] = []
    ld_conf_rocm: List[str] = []
    rocm_libs: List[str] = []
    env_vars: List[str] = []
    clinfo: List[str] = []
    kfd_proc: List[str] = []

    @staticmethod
    def _validate_version_string(version: str) -> str:
        if not _ROCM_VERSION_RE.match(version):
            raise ValueError(f"ROCm version has invalid format: {version}")
        return version

    @field_validator("rocm_version")
    @classmethod
    def validate_rocm_version(cls, rocm_version: str) -> str:
        return cls._validate_version_string(rocm_version)

    @field_validator("rocm_sub_versions")
    @classmethod
    def validate_rocm_sub_versions(cls, sub_versions: dict[str, str]) -> dict[str, str]:
        for version in sub_versions.values():
            cls._validate_version_string(version)
        return sub_versions

    @computed_field
    def build_number(self) -> Optional[str]:
        """Build tag from version-rocm sub-version, or rocm_version when absent."""
        rocm_version = self.rocm_sub_versions.get(self.ROCM_VERSION_FILENAME, self.rocm_version)
        if "-" in rocm_version:
            return rocm_version.split("-")[1]
        return None
