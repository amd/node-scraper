###############################################################################
#
# MIT License
#
# Copyright (c) 2026 Advanced Micro Devices, Inc.
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
from typing import Optional, Union

from nodescraper.enums import EventCategory, EventPriority, ExecutionStatus
from nodescraper.interfaces import DataAnalyzer
from nodescraper.models import TaskResult

from .analyzer_args import CCompileRunAnalyzerArgs
from .c_compile_run_data import CCompileRunDataModel


def _as_list(value: Union[str, list[str]]) -> list[str]:
    if isinstance(value, str):
        return [value]
    return list(value)


class CCompileRunAnalyzer(DataAnalyzer[CCompileRunDataModel, CCompileRunAnalyzerArgs]):
    """Validate C compile/run exit codes and optional run stdout content."""

    DATA_MODEL = CCompileRunDataModel

    DOCUMENTATION_ANALYSIS_ITEMS: tuple[str, ...] = (
        "Checks compile and run exit codes against analysis_args expected values.",
        "Optional run_must_contain / run_must_not_contain checks on run stdout.",
    )

    def analyze_data(
        self,
        data: CCompileRunDataModel,
        args: Optional[CCompileRunAnalyzerArgs] = None,
    ) -> TaskResult:
        if args is None:
            args = CCompileRunAnalyzerArgs()

        failures: list[str] = []

        if data.compile.exit_code != args.expected_compile_exit_code:
            failures.append(
                "compile exit code "
                f"{data.compile.exit_code} != expected {args.expected_compile_exit_code}"
            )

        if data.run is None:
            if data.compile.success:
                failures.append("run was not executed after successful compile")
        else:
            if data.run.exit_code != args.expected_run_exit_code:
                failures.append(
                    "run exit code "
                    f"{data.run.exit_code} != expected {args.expected_run_exit_code}"
                )

            stdout = data.run.stdout or ""
            if args.run_must_contain is not None:
                for needle in _as_list(args.run_must_contain):
                    if needle not in stdout:
                        failures.append(f"run stdout missing required text: {needle!r}")

            if args.run_must_not_contain is not None:
                for needle in _as_list(args.run_must_not_contain):
                    if needle in stdout:
                        failures.append(f"run stdout contains forbidden text: {needle!r}")

        if failures:
            for message in failures:
                self._log_event(
                    category=EventCategory.RUNTIME,
                    description=f"CCompileRun check failed: {message}",
                    priority=EventPriority.ERROR,
                    console_log=True,
                )
            self.result.message = f"CCompileRun: {len(failures)} check(s) failed"
            self.result.status = ExecutionStatus.ERROR
            return self.result

        self.result.message = "CCompileRun checks passed"
        self.result.status = ExecutionStatus.OK
        return self.result
