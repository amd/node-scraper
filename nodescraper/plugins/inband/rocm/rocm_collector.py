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
from nodescraper.connection.inband import TextFileArtifact
from nodescraper.enums import EventCategory, EventPriority, ExecutionStatus, OSFamily
from nodescraper.models import TaskResult
from nodescraper.utils import strip_ansi_codes

from .rocmdata import RocmDataModel


class RocmCollector(InBandDataCollector[RocmDataModel, None]):
    """Collect ROCm version data"""

    SUPPORTED_OS_FAMILY: set[OSFamily] = {OSFamily.LINUX}

    DATA_MODEL = RocmDataModel
    CMD_VERSION_PATHS = [
        "/opt/rocm/.info/version-rocm",
        "/opt/rocm/.info/version",
    ]
    CMD_ROCM_SUB_VERSIONS = "grep . -r /opt/rocm/.info/*"
    CMD_ROCMINFO = "{rocm_path}/bin/rocminfo"
    CMD_ROCM_LATEST = "ls -v -d /opt/rocm-[3-7]* | tail -1"
    CMD_ROCM_DIRS = "ls -v -d /opt/rocm*"
    CMD_LD_CONF = "grep -i -E 'rocm' /etc/ld.so.conf.d/*"
    CMD_ROCM_LIBS = "ldconfig -p | grep -i -E 'rocm'"
    CMD_ENV_VARS = "env | grep -Ei 'rocm|hsa|hip|mpi|openmp|ucx|miopen'"
    CMD_CLINFO = "{rocm_path}/opencl/bin/*/clinfo"
    CMD_KFD_PROC = "ls /sys/class/kfd/kfd/proc/"

    def collect_data(self, args=None) -> tuple[TaskResult, Optional[RocmDataModel]]:
        """Collect ROCm version data from the system.

        Returns:
            tuple[TaskResult, Optional[RocmDataModel]]: tuple containing the task result and ROCm data model if available.
        """
        rocm_data = None
        rocm_sub_versions = {}

        # First, try to collect all sub-versions
        sub_versions_res = self._run_sut_cmd(self.CMD_ROCM_SUB_VERSIONS)
        if sub_versions_res.exit_code == 0:
            for line in sub_versions_res.stdout.splitlines():
                if ":" in line:
                    # Split the line into key and value (format: /path/to/file:version)
                    key, value = line.split(":", 1)
                    # Extract just the filename from the path
                    key = key.split("/")[-1]
                    rocm_sub_versions[key.strip()] = value.strip()

        # Determine the main ROCm version
        for path in self.CMD_VERSION_PATHS:
            res = self._run_sut_cmd(f"grep . {path}")
            if res.exit_code == 0:
                try:
                    rocm_data = RocmDataModel(
                        rocm_version=res.stdout, rocm_sub_versions=rocm_sub_versions
                    )
                    self._log_event(
                        category="ROCM_VERSION_READ",
                        description="ROCm version data collected",
                        data=rocm_data.model_dump(include={"rocm_version"}),
                        priority=EventPriority.INFO,
                    )
                    self.result.message = f"ROCm version: {rocm_data.rocm_version}"
                    self.result.status = ExecutionStatus.OK
                    break
                except ValueError as e:
                    self._log_event(
                        category=EventCategory.OS,
                        description=f"Invalid ROCm version format: {res.stdout}",
                        data={"version": res.stdout, "error": str(e)},
                        priority=EventPriority.ERROR,
                        console_log=True,
                    )
                    self.result.message = f"Invalid ROCm version format: {res.stdout}"
                    self.result.status = ExecutionStatus.ERROR
                    return self.result, None
        else:
            self._log_event(
                category=EventCategory.OS,
                description=f"Unable to read ROCm version from {self.CMD_VERSION_PATHS}",
                data={"raw_output": res.stdout},
                priority=EventPriority.ERROR,
            )

        # Collect additional ROCm data if version was found
        if rocm_data:
            # Collect latest versioned ROCm path (rocm-[3-7]*)
            versioned_path_res = self._run_sut_cmd(self.CMD_ROCM_LATEST)
            if versioned_path_res.exit_code == 0:
                rocm_data.rocm_latest_versioned_path = versioned_path_res.stdout.strip()

            # Collect all ROCm paths as list
            all_paths_res = self._run_sut_cmd(self.CMD_ROCM_DIRS)
            if all_paths_res.exit_code == 0:
                rocm_data.rocm_all_paths = [
                    path.strip()
                    for path in all_paths_res.stdout.strip().split("\n")
                    if path.strip()
                ]

            # Determine ROCm path for commands that need it
            rocm_path = rocm_data.rocm_latest_versioned_path or "/opt/rocm"

            # Collect rocminfo output as list of lines with ANSI codes stripped
            rocminfo_cmd = self.CMD_ROCMINFO.format(rocm_path=rocm_path)
            rocminfo_res = self._run_sut_cmd(rocminfo_cmd)
            rocminfo_artifact_content = ""
            if rocminfo_res.exit_code == 0:
                # Split into lines and strip ANSI codes from each line
                rocm_data.rocminfo = [
                    strip_ansi_codes(line) for line in rocminfo_res.stdout.strip().split("\n")
                ]
                rocminfo_artifact_content += "=" * 80 + "\n"
                rocminfo_artifact_content += "ROCMNFO OUTPUT\n"
                rocminfo_artifact_content += "=" * 80 + "\n\n"
                rocminfo_artifact_content += rocminfo_res.stdout

            # Collect ld.so.conf ROCm entries
            ld_conf_res = self._run_sut_cmd(self.CMD_LD_CONF)
            if ld_conf_res.exit_code == 0:
                rocm_data.ld_conf_rocm = [
                    line.strip() for line in ld_conf_res.stdout.strip().split("\n") if line.strip()
                ]

            # Collect ROCm libraries from ldconfig
            rocm_libs_res = self._run_sut_cmd(self.CMD_ROCM_LIBS)
            if rocm_libs_res.exit_code == 0:
                rocm_data.rocm_libs = [
                    line.strip()
                    for line in rocm_libs_res.stdout.strip().split("\n")
                    if line.strip()
                ]

            # Collect ROCm-related environment variables
            env_vars_res = self._run_sut_cmd(self.CMD_ENV_VARS)
            if env_vars_res.exit_code == 0:
                rocm_data.env_vars = [
                    line.strip() for line in env_vars_res.stdout.strip().split("\n") if line.strip()
                ]

            # Collect clinfo output
            clinfo_cmd = self.CMD_CLINFO.format(rocm_path=rocm_path)
            clinfo_res = self._run_sut_cmd(clinfo_cmd)

            # Always append clinfo section to artifact, even if empty or failed
            if rocminfo_artifact_content:
                rocminfo_artifact_content += "\n\n"
            rocminfo_artifact_content += "=" * 80 + "\n"
            rocminfo_artifact_content += "CLINFO OUTPUT\n"
            rocminfo_artifact_content += "=" * 80 + "\n\n"

            if clinfo_res.exit_code == 0:
                rocm_data.clinfo = [
                    strip_ansi_codes(line) for line in clinfo_res.stdout.strip().split("\n")
                ]
                rocminfo_artifact_content += clinfo_res.stdout
            else:
                # Add error information if clinfo failed
                rocminfo_artifact_content += f"Command: {clinfo_res.command}\n"
                rocminfo_artifact_content += f"Exit Code: {clinfo_res.exit_code}\n"
                if clinfo_res.stderr:
                    rocminfo_artifact_content += f"Error: {clinfo_res.stderr}\n"
                if clinfo_res.stdout:
                    rocminfo_artifact_content += f"Output: {clinfo_res.stdout}\n"

            # Add combined rocminfo and clinfo output as a text file artifact
            if rocminfo_artifact_content:
                self.result.artifacts.append(
                    TextFileArtifact(filename="rocminfo.log", contents=rocminfo_artifact_content)
                )

            # Collect KFD process list
            kfd_proc_res = self._run_sut_cmd(self.CMD_KFD_PROC)
            if kfd_proc_res.exit_code == 0:
                rocm_data.kfd_proc = [
                    proc.strip() for proc in kfd_proc_res.stdout.strip().split("\n") if proc.strip()
                ]

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
