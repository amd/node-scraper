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
from nodescraper.connection.inband.inband import CommandArtifact
from nodescraper.enums import EventCategory, EventPriority, ExecutionStatus, OSFamily
from nodescraper.models import TaskResult

from .kernel_module_data import KernelModuleDataModel


class KernelModuleCollector(InBandDataCollector[KernelModuleDataModel, None]):
    """Read kernel modules and associated parameters"""

    DATA_MODEL = KernelModuleDataModel
    CMD_WINDOWS = "wmic os get Version /Value"
    CMD = "cat /proc/modules"

    def parse_proc_modules(self, output: dict) -> dict:
        """Parse command output and return dict of modules

        Args:
            output (dict): sut cmd output

        Returns:
            dict: parsed modules
        """
        modules = {}
        for line in output.strip().splitlines():
            parts = line.split()
            if not parts:
                continue
            name = parts[0]
            modules[name] = {
                "parameters": {},
            }
        return modules

    def get_module_parameters(self, module_name: str) -> dict:
        """Fetches parameter names and values for a given kernel module using _run_sut_cmd

        Args:
            module_name (str): name of module to fetch params for

        Returns:
            dict: param dict of module
        """
        param_dict = {}
        param_dir = f"/sys/module/{module_name}/parameters"

        list_params_cmd = f"ls {param_dir}"
        res = self._run_sut_cmd(list_params_cmd)
        if res.exit_code != 0:
            return param_dict

        for param in res.stdout.strip().splitlines():
            param_path = f"{param_dir}/{param}"
            value_res = self._run_sut_cmd(f"cat {param_path}")
            value = value_res.stdout.strip() if value_res.exit_code == 0 else "<unreadable>"
            param_dict[param] = value

        return param_dict

    def collect_all_module_info(self) -> tuple[dict, CommandArtifact]:
        """Get all modules and its associated params and values

        Raises:
            RuntimeError: error for failing to get modules

        Returns:
            tuple[dict, CommandArtifact]: modules found and exit code
        """
        modules = {}
        res = self._run_sut_cmd(self.CMD)
        if res.exit_code != 0:
            self._log_event(
                category=EventCategory.OS,
                description="Failed to read /proc/modules",
                data={"command": res.command, "exit_code": res.exit_code},
                priority=EventPriority.ERROR,
                console_log=True,
            )
            return modules

        modules = self.parse_proc_modules(res.stdout)

        for mod in modules:
            modules[mod]["parameters"] = self.get_module_parameters(mod)

        if not modules:
            self._log_event(
                category=EventCategory.OS,
                description="Error checking kernel modules",
                data={"command": res.command, "exit_code": res.exit_code},
                priority=EventPriority.ERROR,
                console_log=True,
            )

        return modules

    def collect_data(self, args=None) -> tuple[TaskResult, Optional[KernelModuleDataModel]]:
        """
        Collect kernel modules data.

        Returns:
            tuple[TaskResult, Optional[KernelModuleDataModel]]: tuple containing the task result and kernel data model or None if not found.
        """
        kernel_modules = {}
        km_data: KernelModuleDataModel | None = None
        if self.system_info.os_family == OSFamily.WINDOWS:
            res = self._run_sut_cmd(self.CMD_WINDOWS)
            if res.exit_code == 0:
                for line in res.stdout.splitlines():
                    if line.startswith("Version="):
                        version = line.split("=", 1)[1]
                        kernel_modules = {version: {"parameters": {}}}
                        break

        else:
            kernel_modules = self.collect_all_module_info()

        if kernel_modules:
            km_data = KernelModuleDataModel(kernel_modules=kernel_modules)
            self._log_event(
                category="KERNEL_READ",
                description="Kernel modules read",
                data=km_data.model_dump(),
                priority=EventPriority.INFO,
            )
            self.result.message = f"{len(km_data.kernel_modules)} kernel modules collected"
            self.result.status = ExecutionStatus.OK
        else:
            self.result.message = "Kernel modules not found"
            self.result.status = ExecutionStatus.ERROR

        return self.result, km_data
