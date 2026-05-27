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
from typing import List, Optional

from pydantic import field_validator

from nodescraper.models import DataModel

# e.g. 7.13.0, 7.13.0-123, 7.13.0-123-gfx942, 7.13.0-123-gfx942;gfx950
_ROCM_VERSION_RE = re.compile(r"^\d+(?:\.\d+){0,3}(?:-\d+)?(?:-gfx\d+(?:;gfx\d+)*)?$")
_ROCM_BUILD_NUMBER_RE = re.compile(r"^\d+(?:\.\d+){0,3}-(\d+)")


def _validate_rocm_version_string(rocm_version: str) -> str:
    if not _ROCM_VERSION_RE.match(rocm_version):
        raise ValueError(f"ROCm version has invalid format: {rocm_version}")
    return rocm_version


class RocmDataModel(DataModel):
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

    @field_validator("rocm_version")
    @classmethod
    def validate_rocm_version(cls, rocm_version: str) -> str:
        """
        Validate the ROCm version format.

        Args:
            rocm_version (str): The ROCm version string to validate.

        Raises:
            ValueError: If the ROCm version does not match the expected format.

        Returns:
            str: The validated ROCm version string.
        """
        return _validate_rocm_version_string(rocm_version)

    @field_validator("rocm_sub_versions")
    @classmethod
    def validate_rocm_sub_versions(cls, rocm_sub_versions: dict[str, str]) -> dict[str, str]:
        for value in rocm_sub_versions.values():
            _validate_rocm_version_string(value)
        return rocm_sub_versions

    @property
    def build_number(self) -> Optional[str]:
        """ROCm package build number from version-rocm sub-version or rocm_version."""
        version_str = self.rocm_sub_versions.get("version-rocm") or self.rocm_version
        match = _ROCM_BUILD_NUMBER_RE.match(version_str)
        return match.group(1) if match else None
