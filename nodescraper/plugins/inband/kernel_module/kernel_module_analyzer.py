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
from typing import Optional

from nodescraper.enums import EventCategory, EventPriority, ExecutionStatus
from nodescraper.interfaces import DataAnalyzer
from nodescraper.models import TaskResult

from .analyzer_args import KernelModuleAnalyzerArgs
from .kernel_module_data import KernelModuleDataModel


class KernelModuleAnalyzer(DataAnalyzer[KernelModuleDataModel, KernelModuleAnalyzerArgs]):
    """Check kernel matches expected versions"""

    DATA_MODEL = KernelModuleDataModel

    def filter_modules_by_pattern(
        self, modules: dict[str, dict], patterns: list[str]
    ) -> dict[str, dict]:
        pattern_regex = re.compile("|".join(patterns), re.IGNORECASE)

        return {name: data for name, data in modules.items() if pattern_regex.search(name)}

    def filter_modules_by_name(
        self, modules: dict[str, dict], names: list[str] = None
    ) -> dict[str, dict]:

        if not names:
            return {name: data for name, data in modules.items()}

        return {name: data for name, data in modules.items() if name in names}

    def analyze_data(
        self, data: KernelModuleDataModel, args: Optional[KernelModuleAnalyzerArgs] = None
    ) -> TaskResult:
        """Analyze the kernel modules and associated parameters.

        Args:
            data (KernelModuleDataModel): KernelModule data to analyze.
            args (Optional[KernelModuleAnalyzerArgs], optional): KernelModule analyzer args.

        Returns:
            TaskResult: Result of the analysis containing status and message.
        """
        if not args:
            args = KernelModuleAnalyzerArgs()

        self.result.message = "Kernel modules analyzed"
        self.result.status = ExecutionStatus.OK
        filtered_modules = {}
        if args.regex_match:
            try:
                filtered_modules = self.filter_modules_by_pattern(
                    data.kernel_modules, args.modules_filter
                )
            except re.error:
                self._log_event(
                    category=EventCategory.RUNTIME,
                    description="KernelModule regex is invalid",
                    data=data,
                    priority=EventPriority.ERROR,
                )
                self.result.message = "Kernel modules failed to match regex"
                self.result.status = ExecutionStatus.ERROR
                return self.result

        else:
            filtered_modules = self.filter_modules_by_name(data.kernel_modules, args.modules_filter)

        self._log_event(
            category=EventCategory.RUNTIME,
            description="KernelModules analyzed",
            data=filtered_modules,
            priority=EventPriority.INFO,
        )
        return self.result
