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
import shlex
from typing import Optional

from nodescraper.base import InBandDataCollector
from nodescraper.enums import EventCategory, EventPriority, ExecutionStatus, OSFamily
from nodescraper.models import TaskResult

from .c_compile_run_data import CCompileRunDataModel, CommandPhaseResult
from .collector_args import CCompileRunCollectorArgs


def _shell_command(argv: list[str], work_dir: Optional[str] = None) -> str:
    """Build a safely quoted shell command, optionally prefixed with cd."""
    body = " ".join(shlex.quote(part) for part in argv)
    if work_dir:
        return f"cd {shlex.quote(work_dir)} && {body}"
    return body


def _build_compile_command(args: CCompileRunCollectorArgs, output_path: str) -> str:
    """Return the gcc compile command for args and output_path."""
    argv = [args.gcc, *args.gcc_extra_args, "-o", output_path, args.source_path]
    return _shell_command(argv, args.work_dir)


def _build_run_command(args: CCompileRunCollectorArgs, output_path: str) -> str:
    """Return the command that executes the compiled binary."""
    argv = [output_path, *args.run_args]
    return _shell_command(argv, args.work_dir)


class CCompileRunCollector(InBandDataCollector[CCompileRunDataModel, CCompileRunCollectorArgs]):
    """Compile a .c file on the target and execute the resulting binary."""

    DATA_MODEL = CCompileRunDataModel
    SUPPORTED_OS_FAMILY: set[OSFamily] = {OSFamily.LINUX}

    DOCUMENTATION_COLLECTION_ITEMS: tuple[str, ...] = (
        "Compiles collection_args.source_path with gcc and collection_args.gcc_extra_args.",
        "Executes the output binary with collection_args.run_args when compile succeeds.",
    )

    def collect_data(
        self, args: Optional[CCompileRunCollectorArgs] = None
    ) -> tuple[TaskResult, Optional[CCompileRunDataModel]]:
        if args is None or not args.source_path:
            self.result.message = "source_path is required in collection_args"
            self.result.status = ExecutionStatus.NOT_RAN
            return self.result, None

        output_path = args.resolved_output_path()
        compile_command = _build_compile_command(args, output_path)
        compile_res = self._run_sut_cmd(
            compile_command,
            sudo=args.compile_sudo,
            timeout=args.compile_timeout,
        )
        compile_phase = CommandPhaseResult(
            command=compile_command,
            exit_code=compile_res.exit_code,
            success=compile_res.exit_code == 0,
            stdout=compile_res.stdout if args.include_stdout else None,
            stderr=compile_res.stderr or None,
        )

        if compile_phase.success:
            self._log_event(
                category=EventCategory.RUNTIME,
                description="C compile succeeded",
                data={
                    "source_path": args.source_path,
                    "output_path": output_path,
                    "command": compile_command,
                },
                priority=EventPriority.INFO,
            )
        else:
            self._log_event(
                category=EventCategory.RUNTIME,
                description="C compile failed",
                data={
                    "source_path": args.source_path,
                    "output_path": output_path,
                    "command": compile_command,
                    "exit_code": compile_res.exit_code,
                    "stderr": compile_res.stderr,
                },
                priority=EventPriority.ERROR,
                console_log=True,
            )
            self.result.message = "C compile failed"
            self.result.status = ExecutionStatus.ERROR
            return self.result, CCompileRunDataModel(
                source_path=args.source_path,
                output_path=output_path,
                compile=compile_phase,
                run=None,
            )

        run_command = _build_run_command(args, output_path)
        run_res = self._run_sut_cmd(
            run_command,
            sudo=args.run_sudo,
            timeout=args.run_timeout,
        )
        run_phase = CommandPhaseResult(
            command=run_command,
            exit_code=run_res.exit_code,
            success=run_res.exit_code == 0,
            stdout=run_res.stdout if args.include_stdout else None,
            stderr=run_res.stderr or None,
        )

        if run_phase.success:
            self._log_event(
                category=EventCategory.RUNTIME,
                description="Compiled binary executed successfully",
                data={"output_path": output_path, "command": run_command},
                priority=EventPriority.INFO,
            )
            self.result.message = "C compile and run succeeded"
            self.result.status = ExecutionStatus.OK
        else:
            self._log_event(
                category=EventCategory.RUNTIME,
                description="Compiled binary execution failed",
                data={
                    "output_path": output_path,
                    "command": run_command,
                    "exit_code": run_res.exit_code,
                    "stderr": run_res.stderr,
                },
                priority=EventPriority.ERROR,
                console_log=True,
            )
            self.result.message = "Compiled binary execution failed"
            self.result.status = ExecutionStatus.ERROR

        return self.result, CCompileRunDataModel(
            source_path=args.source_path,
            output_path=output_path,
            compile=compile_phase,
            run=run_phase,
        )
