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
        self, modules: dict[str, dict], patterns: list[str] = None
    ) -> tuple[dict[str, dict], list[str]]:
        """Filter modules by pattern

        Args:
            modules (dict[str, dict]): modules to be filtered
            patterns (list[str], optional): pattern to us. Defaults to None.

        Returns:
            tuple[dict[str, dict], list[str]]: tuple - dict of modules filtered,
            list of unmatched pattern
        """
        if patterns is None:
            return modules, []

        matched_modules = {}
        unmatched_patterns = []

        pattern_match_flags = {p: False for p in patterns}

        for mod_name in modules:
            for p in patterns:
                if re.search(p, mod_name, re.IGNORECASE):
                    matched_modules[mod_name] = modules[mod_name]
                    pattern_match_flags[p] = True
                    break

        unmatched_patterns = [p for p, matched in pattern_match_flags.items() if not matched]

        return matched_modules, unmatched_patterns

    def filter_modules_by_name_and_param(
        self, modules: dict[str, dict], to_match: dict[str, dict]
    ) -> tuple[dict[str, dict], dict[str, dict]]:
        """Filter modules by name, param and value

        Args:
            modules (dict[str, dict]): modules to be filtered
            to_match (dict[str, dict]): modules to match

        Returns:
            tuple[dict[str, dict], dict[str, dict]]: tuple - dict of modules filtered,
            dict of modules unmatched
        """
        if not to_match:
            return modules, {}

        filtered = {}
        unmatched = {}

        for mod_name, expected_data in to_match.items():
            expected_params = expected_data.get("parameters", {})
            actual_data = modules.get(mod_name)

            if not actual_data:
                unmatched[mod_name] = expected_data
                continue

            actual_params = actual_data.get("parameters", {})
            param_mismatches = {}

            for param, expected_val in expected_params.items():
                actual_val = actual_params.get(param)
                if actual_val != expected_val:
                    param_mismatches[param] = {
                        "expected": expected_val,
                        "actual": actual_val if actual_val is not None else "<missing>",
                    }

            if param_mismatches:
                unmatched[mod_name] = {"parameters": param_mismatches}
            else:
                filtered[mod_name] = actual_data

        return filtered, unmatched

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
        else:
            if args.regex_filter and args.kernel_modules:
                self.logger.warning(
                    "Both regex_filter and kernel_modules provided in analyzer args. kernel_modules will be ignored"
                )

        self.result.status = ExecutionStatus.OK

        if args.regex_filter:
            try:
                filtered_modules, unmatched_pattern = self.filter_modules_by_pattern(
                    data.kernel_modules, args.regex_filter
                )
            except re.error:
                self._log_event(
                    category=EventCategory.RUNTIME,
                    description=f"KernelModule regex is invalid. Regex: {args.regex_filter}",
                    data={"regex_filters": {args.regex_filter}},
                    priority=EventPriority.ERROR,
                )
                self.result.message = "Kernel modules failed to match regex"
                self.result.status = ExecutionStatus.ERROR
                return self.result

            if unmatched_pattern:
                self._log_event(
                    category=EventCategory.RUNTIME,
                    description=f"KernelModules did not match all patterns. Unmatched patterns: {unmatched_pattern}",
                    data={"unmatched_pattern: ": unmatched_pattern},
                    priority=EventPriority.INFO,
                )
                self.result.message = f"Kernel modules failed to match every pattern. Unmatched patterns: {unmatched_pattern}"
                self.result.status = ExecutionStatus.ERROR
                return self.result

            self._log_event(
                category=EventCategory.OS,
                description="KernelModules analyzed",
                data={"filtered_modules": filtered_modules},
                priority=EventPriority.INFO,
            )
            return self.result

        elif args.kernel_modules:
            filtered_modules, not_matched = self.filter_modules_by_name_and_param(
                data.kernel_modules, args.kernel_modules
            )

            # no modules matched
            if not filtered_modules and not_matched:
                self._log_event(
                    category=EventCategory.RUNTIME,
                    description=f"KernelModules: no modules matched. Not matched: {not_matched}",
                    data=args.kernel_modules,
                    priority=EventPriority.ERROR,
                )
                self.result.message = f"Kernel modules not matched. Not matched: {not_matched}"
                self.result.status = ExecutionStatus.ERROR
                return self.result
            # some modules matched
            elif filtered_modules and not_matched:

                self._log_event(
                    category=EventCategory.RUNTIME,
                    description=f"KernelModules: not all modules matched. Not matched: {not_matched}",
                    data=not_matched,
                    priority=EventPriority.ERROR,
                )
                self.result.message = f"Kernel modules not matched. Not matched: {not_matched}"
                self.result.status = ExecutionStatus.ERROR
                return self.result
        else:
            self.result.message = (
                "No values provided in analysis args for: kernel_modules and regex_match"
            )
            self.result.status = ExecutionStatus.NOT_RAN
            return self.result
