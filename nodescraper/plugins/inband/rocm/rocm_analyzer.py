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
from typing import List, Optional, Tuple, Union

from nodescraper.enums import EventCategory, EventPriority, ExecutionStatus
from nodescraper.interfaces import DataAnalyzer
from nodescraper.models import TaskResult

from .analyzer_args import RocmAnalyzerArgs
from .rocmdata import RocmDataModel


class RocmAnalyzer(DataAnalyzer[RocmDataModel, RocmAnalyzerArgs]):
    """Check ROCm matches expected versions.

    The expected ROCm version (exp_rocm) can be a string or a list of allowed strings.
    Sub-versions (exp_rocm_sub_versions) are a dict: each value can be a string or
    a list of allowed strings for that key.
    """

    DATA_MODEL = RocmDataModel

    def check_exp_rocm_sub_versions(
        self,
        data: RocmDataModel,
        exp_rocm_sub_versions: dict[str, Union[str, list]],
    ) -> bool:
        """Check if ROCm sub-versions match expected versions when provided.

        Each expected value can be a single string (exact match) or a list of
        allowed strings (actual must be in the list).

        Returns:
            bool: True if all sub-versions match, False otherwise
        """
        events: dict[str, Tuple[Union[str, List[str]], str]] = {}  # {Version: (expected, actual)}
        for exp_version_key, exp_rocm in exp_rocm_sub_versions.items():
            actual_version = data.rocm_sub_versions.get(exp_version_key)
            if actual_version is None:
                events[exp_version_key] = (
                    exp_rocm,
                    "Not Available",
                )
                continue

            if isinstance(exp_rocm, list) and actual_version not in exp_rocm:
                events[exp_version_key] = (
                    exp_rocm,
                    actual_version,
                )
            elif actual_version != exp_rocm:
                events[exp_version_key] = (
                    exp_rocm,
                    actual_version,
                )
        if events:
            self._log_event(
                category=EventCategory.SW_DRIVER,
                description="ROCm sub-version mismatch!",
                data={
                    "expected": {k: r[0] for k, r in events.items()},
                    "actual": {k: r[1] for k, r in events.items()},
                },
                priority=EventPriority.ERROR,
                console_log=True,
            )
            return False
        return True

    def analyze_data(
        self, data: RocmDataModel, args: Optional[RocmAnalyzerArgs] = None
    ) -> TaskResult:
        """
        Analyze the provided ROCm data against expected versions.

        Args:
            data (RocmDataModel): ROCm data to analyze
            args (Optional[RocmAnalyzerArgs], optional): ROCm analysis arguments. Defaults to None.

        Returns:
            TaskResult: Result of the analysis containing status and message.
        """
        if args is None:
            args = RocmAnalyzerArgs()

        exp_rocm = args.exp_rocm
        exp_rocm_sub_versions = args.exp_rocm_sub_versions
        exp_rocm_latest = args.exp_rocm_latest

        if not exp_rocm and not exp_rocm_sub_versions and not exp_rocm_latest:
            self.result.message = "Expected ROCm not provided"
            self.result.status = ExecutionStatus.NOT_RAN
            return self.result

        errors: List[str] = []

        if exp_rocm and data.rocm_version not in exp_rocm:
            self._log_event(
                category=EventCategory.SW_DRIVER,
                description=f"ROCm version mismatch! Expected: {exp_rocm}, actual: {data.rocm_version}",
                data={"expected": exp_rocm, "actual": data.rocm_version},
                priority=EventPriority.CRITICAL,
                console_log=True,
            )
            errors.append("ROCm version mismatch!")

        if exp_rocm_sub_versions and not self.check_exp_rocm_sub_versions(
            data=data,
            exp_rocm_sub_versions=exp_rocm_sub_versions,
        ):
            errors.append("ROCm sub-version mismatch")

        if exp_rocm_latest and data.rocm_latest_versioned_path != exp_rocm_latest:
            self._log_event(
                category=EventCategory.SW_DRIVER,
                description=f"ROCm latest path mismatch! Expected: {exp_rocm_latest}, actual: {data.rocm_latest_versioned_path}",
                data={
                    "expected": exp_rocm_latest,
                    "actual": data.rocm_latest_versioned_path,
                },
                priority=EventPriority.CRITICAL,
                console_log=True,
            )
            errors.append(
                f"ROCm latest path mismatch! Expected: {exp_rocm_latest}, actual: {data.rocm_latest_versioned_path}"
            )

        if errors:
            self.result.status = ExecutionStatus.ERROR
            self.result.message = ". ".join(errors)
        else:
            self.result.status = ExecutionStatus.OK
            success_parts = []
            if exp_rocm:
                success_parts.append("ROCm version matches expected")
            if exp_rocm_sub_versions:
                success_parts.append("ROCm sub-versions match expected")
            if exp_rocm_latest:
                success_parts.append(
                    f"ROCm latest path validated: {data.rocm_latest_versioned_path}"
                )
            self.result.message = ". ".join(success_parts)

        return self.result
