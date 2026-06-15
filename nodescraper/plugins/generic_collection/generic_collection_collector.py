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
from typing import Optional

from nodescraper.base import InBandDataCollector
from nodescraper.enums import EventCategory, EventPriority, ExecutionStatus, OSFamily
from nodescraper.models import TaskResult

from .collector_args import GenericCollectionCollectorArgs
from .generic_collection_data import CommandCollectionResult, GenericCollectionDataModel


class GenericCollectionCollector(
    InBandDataCollector[GenericCollectionDataModel, GenericCollectionCollectorArgs]
):
    """Run user-configured shell commands and report per-command success."""

    DATA_MODEL = GenericCollectionDataModel
    SUPPORTED_OS_FAMILY: set[OSFamily] = {OSFamily.WINDOWS, OSFamily.LINUX, OSFamily.UNKNOWN}

    DOCUMENTATION_COLLECTION_ITEMS: tuple[str, ...] = (
        "Runs each command from collection_args.commands on the target (in-band host or BMC over OOB SSH).",
        "Commands are user-configured; there are no fixed CMD_* class fields.",
    )

    def collect_data(
        self, args: Optional[GenericCollectionCollectorArgs] = None
    ) -> tuple[TaskResult, Optional[GenericCollectionDataModel]]:
        if args is None:
            args = GenericCollectionCollectorArgs()

        if not args.commands:
            self.result.message = "No commands configured"
            self.result.status = ExecutionStatus.NOT_RAN
            return self.result, None

        results: list[CommandCollectionResult] = []
        for cmd_spec in args.commands:
            command = cmd_spec.command.strip()
            if not command:
                continue

            sudo = cmd_spec.sudo if cmd_spec.sudo is not None else args.sudo
            timeout = cmd_spec.timeout if cmd_spec.timeout is not None else args.timeout
            include_stdout = (
                cmd_spec.include_stdout
                if cmd_spec.include_stdout is not None
                else args.include_stdout
            )
            res = self._run_sut_cmd(
                command,
                sudo=sudo,
                timeout=timeout,
            )
            success = res.exit_code == 0
            cmd_result = CommandCollectionResult(
                name=cmd_spec.name,
                command=command,
                success=success,
                exit_code=res.exit_code,
                sudo=sudo,
                stdout=res.stdout if include_stdout else None,
                stderr=res.stderr or None,
            )
            results.append(cmd_result)

            if success:
                self._log_event(
                    category=EventCategory.RUNTIME,
                    description=f"Command succeeded: {command!r}",
                    data={
                        "name": cmd_spec.name,
                        "command": command,
                        "exit_code": res.exit_code,
                        "sudo": sudo,
                    },
                    priority=EventPriority.INFO,
                )
            else:
                self._log_event(
                    category=EventCategory.RUNTIME,
                    description=f"Command failed: {command!r}",
                    data={
                        "name": cmd_spec.name,
                        "command": command,
                        "exit_code": res.exit_code,
                        "sudo": sudo,
                        "stderr": res.stderr,
                    },
                    priority=EventPriority.ERROR,
                    console_log=True,
                )

        if not results:
            self.result.message = "No commands configured"
            self.result.status = ExecutionStatus.NOT_RAN
            return self.result, None

        success_count = sum(1 for result in results if result.success)
        total = len(results)
        self.result.message = f"Generic collection: {success_count}/{total} commands succeeded"
        self.result.status = ExecutionStatus.OK if success_count == total else ExecutionStatus.ERROR
        return self.result, GenericCollectionDataModel(results=results)
