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
import json
import re
from enum import Enum
from typing import Optional

from nodescraper.base import InBandDataCollector
from nodescraper.connection.inband import TextFileArtifact
from nodescraper.enums import EventCategory, EventPriority, ExecutionStatus, OSFamily
from nodescraper.models import TaskResult
from nodescraper.utils import shell_quote, strip_ansi_codes

from .collector_args import RocmCollectorArgs
from .rocmdata import _ROCK_PKGMGR_RE, RocmDataModel


class InstallationType(Enum):
    ROCm_CI = "ROCm_CI"
    TheRock_PkgMgr = "TheRock_PkgMgr"


class RocmCollector(InBandDataCollector[RocmDataModel, RocmCollectorArgs]):
    """Collect ROCm version data"""

    SUPPORTED_OS_FAMILY: set[OSFamily] = {OSFamily.LINUX}

    DATA_MODEL = RocmDataModel
    ROCM_VERSION_SPECIAL = "version"
    CMD_ROCM_SUB_VERSIONS_TMPL = "grep . -H -r -i {rocm_path}/.info/*"
    CMD_ROCMINFO_TMPL = "{rocm_path}/bin/rocminfo"
    CMD_ROCM_LATEST_TMPL = "ls -v -d {rocm_path}-[3-7]* | tail -1"
    CMD_ROCM_DIRS_TMPL = "ls -v -d {rocm_path}*"
    CMD_LD_CONF = "grep -i -E 'rocm' /etc/ld.so.conf.d/*"
    CMD_ROCM_LIBS = "ldconfig -p | grep -i -E 'rocm'"
    CMD_ENV_VARS = "env | grep -Ei 'rocm|hsa|hip|mpi|openmp|ucx|miopen'"
    CMD_CLINFO_TMPL = "{rocm_path}/opencl/bin/*/clinfo"
    CMD_KFD_PROC = "ls /sys/class/kfd/kfd/proc/"
    CMD_THEROCK_MANIFEST_TMPL = "{rocm_path}/share/therock/therock_manifest.json"
    CMD_THEROCK_CORE_VERSION_TMPL = "{rocm_path}/core/.info/version"

    def collect_data(
        self, args: Optional[RocmCollectorArgs] = None
    ) -> tuple[TaskResult, Optional[RocmDataModel]]:
        """Collect ROCm version data from the system.

        Returns:
            tuple[TaskResult, Optional[RocmDataModel]]: tuple containing the task result and ROCm data model if available.
        """
        if args is None:
            args = RocmCollectorArgs()
        rocm_path_q = shell_quote(args.rocm_path)

        install_type = None
        # Check if legacy or TheRock install
        res_legacy_check = self._run_sut_cmd(f"test -f {rocm_path_q}/.info/version")
        if res_legacy_check.exit_code == 0:
            install_type = InstallationType.ROCm_CI
        else:
            res_rock_check = self._run_sut_cmd(
                f"test -f {rocm_path_q}/share/therock/therock_manifest.json"
            )
            if res_rock_check.exit_code == 0:
                install_type = InstallationType.TheRock_PkgMgr

        error = None
        rocm_data = None
        if install_type == InstallationType.TheRock_PkgMgr:
            res = self._run_sut_cmd(f"cat {rocm_path_q}/share/therock/therock_manifest.json")
            try:
                json_data = json.loads(res.stdout)
            except json.JSONDecodeError as e:
                error = {
                    "description": "Invalid JSON in therock_manifest.json",
                    "data": {
                        "message": f"Parse error at line {e.lineno}, col {e.colno}",
                        "exception": str(e),
                        "raw_content": res.stdout[:500] if res.stdout else None,
                    },
                }
                json_data = None
            if json_data is not None:
                # ROCm package version
                rocm_package_version = json_data.get("rocm_package_version", "")
                # ROCm version
                if "rocm_version" in json_data:
                    rocm_version = json_data["rocm_version"]
                else:
                    if not isinstance(rocm_package_version, str):
                        rocm_version = None
                    else:
                        match = re.search(
                            _ROCK_PKGMGR_RE,
                            rocm_package_version,
                        )
                        rocm_version = match.group(2) if match else None
                if rocm_version is None:
                    res = self._run_sut_cmd(f"cat {rocm_path_q}/core/.info/version")
                    if res.stdout:
                        rocm_version = res.stdout.strip()
                # Build number
                raw_build_number = json_data.get("github_run_id")
                try:
                    build_number = int(raw_build_number)
                except (ValueError, TypeError):
                    build_number = None
                if build_number is None and raw_build_number is not None:
                    error = {
                        "description": "Invalid github_run_id in therock_manifest.json",
                        "data": {
                            "message": f"Cannot convert {type(raw_build_number).__name__} to int",
                            "rocm_version": rocm_version,
                            "build_number": raw_build_number,
                        },
                    }
                elif rocm_version is None or build_number is None:
                    error = {
                        "description": "Missing ROCm version or build number",
                        "data": {
                            "message": "Required fields not found in therock_manifest.json",
                            "rocm_version": rocm_version,
                            "build_number": build_number,
                        },
                    }
                else:
                    sub_versions = {
                        "version": rocm_version,
                        "version-rocm": f"{rocm_version}-{build_number}",
                    }
                    if rocm_package_version:
                        sub_versions.update({"version-rocm-package": rocm_package_version})
                    rocm_data = RocmDataModel(
                        rocm_version=rocm_version,
                        rocm_sub_versions=sub_versions,
                    )
            elif error is None:
                error = {
                    "description": "Failed to read therock_manifest.json",
                    "data": {
                        "message": "JSON parsed as None",
                    },
                }
        elif install_type == InstallationType.ROCm_CI:
            res = self._run_sut_cmd(f"grep . -H -r -i {rocm_path_q}/.info/*")
            if res.exit_code == 0:
                rocm_sub_versions = {}
                for line in res.stdout.splitlines():
                    if ":" in line:
                        # Split the line into key and value
                        key, value = line.split(":", 1)
                        key = key.removeprefix(f"{args.rocm_path}/.info/")
                        # Remove leading and trailing whitespace
                        rocm_sub_versions[key.strip()] = value.strip()
                if self.ROCM_VERSION_SPECIAL in rocm_sub_versions:
                    # If the special key is found, use its value
                    rocm_version = rocm_sub_versions[self.ROCM_VERSION_SPECIAL]
                else:
                    rocm_version = None
                rocm_data = RocmDataModel(
                    rocm_version=rocm_version, rocm_sub_versions=rocm_sub_versions
                )
            else:
                error = {
                    "description": "Failed to read ROCm .info files",
                    "data": {
                        "command": res.command,
                        "exit_code": res.exit_code,
                        "stderr": res.stderr,
                    },
                }
        else:
            error = {
                "description": "No ROCm installation detected",
                "data": {"message": f"No ROCm files found in {args.rocm_path}"},
            }

        if error:
            self._log_event(
                category=EventCategory.OS,
                description=error.get("description", ""),
                data=error.get("data", {}),
                priority=EventPriority.ERROR,
                console_log=True,
            )
            self.result.message = "ROCm version not found"
            self.result.status = ExecutionStatus.ERROR
        else:
            self._log_event(
                category="ROCM_VERSION_READ",
                description="ROCm version data collected",
                data=rocm_data.model_dump(exclude="rocm_sub_versions"),
                priority=EventPriority.INFO,
            )
            self.result.message = f"ROCm: {rocm_data.model_dump(exclude='rocm_sub_versions')}"
            self.result.status = ExecutionStatus.OK

        # Collect additional ROCm data if version was found
        if rocm_data:
            # Collect latest versioned ROCm path (rocm-[3-7]*)
            versioned_path_res = self._run_sut_cmd(
                self.CMD_ROCM_LATEST_TMPL.format(rocm_path=rocm_path_q)
            )
            if versioned_path_res.exit_code == 0:
                rocm_data.rocm_latest_versioned_path = versioned_path_res.stdout.strip()

            # Collect all ROCm paths as list
            all_paths_res = self._run_sut_cmd(self.CMD_ROCM_DIRS_TMPL.format(rocm_path=rocm_path_q))
            if all_paths_res.exit_code == 0:
                rocm_data.rocm_all_paths = [
                    path.strip()
                    for path in all_paths_res.stdout.strip().split("\n")
                    if path.strip()
                ]

            # Collect rocminfo output as list of lines with ANSI codes stripped
            rocminfo_cmd = self.CMD_ROCMINFO_TMPL.format(rocm_path=rocm_path_q)
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
            clinfo_cmd = self.CMD_CLINFO_TMPL.format(rocm_path=rocm_path_q)
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

        return self.result, rocm_data
