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
from typing import Optional

from nodescraper.base import InBandDataCollector
from nodescraper.enums import EventCategory, EventPriority, ExecutionStatus, OSFamily
from nodescraper.models import TaskResult

from .rocmdata import RocmDataModel


class RocmCollector(InBandDataCollector[RocmDataModel, None]):
    """Collect ROCm version data"""

    SUPPORTED_OS_FAMILY: set[OSFamily] = {OSFamily.LINUX}

    DATA_MODEL = RocmDataModel
    CMD_VERSION_PATHS = [
        "/opt/rocm/.info/version-rocm",
        "/opt/rocm/.info/version",
    ]
    CMD_ROCMINFO = "rocminfo"
    CMD_ROCM_VERSIONED_PATHS = "ls -v -d /opt/rocm-[3-7]* | tail -1"
    CMD_ROCM_ALL_PATHS = "ls -v -d /opt/rocm*"

    def collect_data(self, args=None) -> tuple[TaskResult, Optional[RocmDataModel]]:
        """Collect ROCm version data from the system.

        Returns:
            tuple[TaskResult, Optional[RocmDataModel]]: tuple containing the task result and ROCm data model if available.
        """
        version_paths = [
            "/opt/rocm/.info/version-rocm",
            "/opt/rocm/.info/version",
        ]

        rocm_data = None
        for path in self.CMD_VERSION_PATHS:
            res = self._run_sut_cmd(f"grep . {path}")
            if res.exit_code == 0:
                rocm_data = RocmDataModel(rocm_version=res.stdout)

                # Collect rocminfo output
                rocminfo_res = self._run_sut_cmd(self.CMD_ROCMINFO)
                if rocminfo_res.exit_code == 0:
                    rocm_data.rocminfo = rocminfo_res.stdout

                # Collect latest versioned ROCm path (rocm-[3-7]*)
                versioned_path_res = self._run_sut_cmd(self.CMD_ROCM_VERSIONED_PATHS)
                if versioned_path_res.exit_code == 0:
                    rocm_data.rocm_latest_versioned_path = versioned_path_res.stdout

                # Collect all ROCm paths
                all_paths_res = self._run_sut_cmd(self.CMD_ROCM_ALL_PATHS)
                if all_paths_res.exit_code == 0:
                    rocm_data.rocm_all_paths = all_paths_res.stdout

                self._log_event(
                    category="ROCM_VERSION_READ",
                    description="ROCm version data collected",
                    data=rocm_data.model_dump(),
                    priority=EventPriority.INFO,
                )
                self.result.message = f"ROCm: {rocm_data.model_dump()}"
                self.result.status = ExecutionStatus.OK
                break
        else:
            self._log_event(
                category=EventCategory.OS,
                description=f"Unable to read ROCm version from {version_paths}",
                data={"raw_output": res.stdout},
                priority=EventPriority.ERROR,
            )

        if not rocm_data:
            self._log_event(
                category=EventCategory.OS,
                description="Error checking ROCm version",
                data={
                    "command": res.command,
                    "exit_code": res.exit_code,
                    "stderr": res.stderr,
                },
                priority=EventPriority.ERROR,
                console_log=True,
            )
            self.result.message = "ROCm version not found"
            self.result.status = ExecutionStatus.ERROR

        return self.result, rocm_data
