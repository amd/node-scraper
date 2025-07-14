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
from nodescraper.base import InBandDataCollector
from nodescraper.enums import EventCategory, EventPriority, ExecutionStatus, OSFamily
from nodescraper.models import TaskResult

from .kernel_module_data import KernelModuleDataModel


class KernelModuleCollector(InBandDataCollector[KernelModuleDataModel, None]):
    """Read kernel modules and associated parameters"""

    DATA_MODEL = KernelModuleDataModel

    def parse_proc_modules(self, output):
        """Parses the output of /proc/modules into a dictionary."""
        modules = {}
        for line in output.strip().splitlines():
            parts = line.split()
            if len(parts) < 6:
                continue
            name, size, instances, deps, state, offset = parts[:6]
            modules[name] = {
                "parameters": {},
            }
        return modules

    def get_module_parameters(self, module_name):
        """Fetches parameter names and values for a given kernel module using _run_sut_cmd."""
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

    def collect_all_module_info(self):
        res = self._run_sut_cmd("cat /proc/modules")
        if res.exit_code != 0:
            raise RuntimeError("Failed to read /proc/modules")

        modules = self.parse_proc_modules(res.stdout)

        for mod in modules:
            modules[mod]["parameters"] = self.get_module_parameters(mod)

        return modules, res

    def collect_data(
        self,
        args=None,
    ) -> tuple[TaskResult, KernelModuleDataModel | None]:
        """
        Collect kernel modules data.

        Returns:
            tuple[TaskResult, KernelModuleDataModel | None]: tuple containing the task result and kernel data model or None if not found.
        """
        kernel_modules = {}
        if self.system_info.os_family == OSFamily.WINDOWS:
            res = self._run_sut_cmd("wmic os get Version /Value")
            if res.exit_code == 0:
                kernel_modules = [line for line in res.stdout.splitlines() if "Version=" in line][
                    0
                ].split("=")[1]
        else:
            kernel_modules, res = self.collect_all_module_info()
            """
            for mod, info in kernel_modules.items():
                print(f"Module: {mod}")
                for key, val in info.items():
                    if key == "parameters":
                        print("  Parameters:")
                        for pname, pval in val.items():
                            print(f"    {pname} = {pval}")
                    else:
                        print(f"  {key}: {val}")
                print()
            """

        if not kernel_modules:
            self._log_event(
                category=EventCategory.OS,
                description="Error checking kernel modules",
                data={"command": res.command, "exit_code": res.exit_code},
                priority=EventPriority.ERROR,
                console_log=True,
            )

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
            kernel_modules = None

        self.result.message = (
            "Kernel modules collected" if kernel_modules else "Kernel modules not found"
        )
        self.result.status = ExecutionStatus.OK if kernel_modules else ExecutionStatus.ERROR
        return self.result, km_data
