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
from nodescraper.utils import nice_rotated_name, shell_quote

from .collector_args import DmesgCollectorArgs
from .dmesgdata import DmesgData


class DmesgCollector(InBandDataCollector[DmesgData, DmesgCollectorArgs]):
    """Read dmesg log"""

    SUPPORTED_OS_FAMILY = {OSFamily.LINUX}

    DATA_MODEL = DmesgData

    DMESG_CMD = "dmesg --time-format iso -x"

    DMESG_LOGS_CMD = (
        r"ls -1 /var/log/dmesg* 2>/dev/null | grep -E '^/var/log/dmesg(\.[0-9]+(\.gz)?)?$' || true"
    )

    def _collect_dmesg_rotations(self):
        """Collect dmesg logs"""
        list_res = self._run_sut_cmd(self.DMESG_LOGS_CMD, sudo=True)
        paths = [p.strip() for p in (list_res.stdout or "").splitlines() if p.strip()]
        if not paths:
            self._log_event(
                category=EventCategory.OS,
                description="No /var/log/dmesg files found (including rotations).",
                data={"list_exit_code": list_res.exit_code},
                priority=EventPriority.WARNING,
            )
            return 0

        collected_logs, failed_logs = [], []
        for p in paths:
            qp = shell_quote(p)
            if p.endswith(".gz"):
                cmd = f"gzip -dc {qp} 2>/dev/null || zcat {qp} 2>/dev/null"
                res = self._run_sut_cmd(cmd, sudo=True, log_artifact=False)
                if res.exit_code == 0 and res.stdout is not None:
                    fname = nice_rotated_name(p, "dmesg")
                    self.logger.info("Collected dmesg log: %s", fname)
                    self.result.artifacts.append(
                        TextFileArtifact(filename=fname, contents=res.stdout)
                    )
                    collected_logs.append(
                        {"path": p, "as": fname, "bytes": len(res.stdout.encode("utf-8", "ignore"))}
                    )
                else:
                    failed_logs.append(
                        {"path": p, "exit_code": res.exit_code, "stderr": res.stderr, "cmd": cmd}
                    )
            else:
                cmd = f"cat {qp}"
                res = self._run_sut_cmd(cmd, sudo=True, log_artifact=False)
                if res.exit_code == 0 and res.stdout is not None:
                    fname = nice_rotated_name(p, "dmesg")
                    self.logger.info("Collected dmesg log: %s", fname)
                    self.result.artifacts.append(
                        TextFileArtifact(filename=fname, contents=res.stdout)
                    )
                    collected_logs.append(
                        {"path": p, "as": fname, "bytes": len(res.stdout.encode("utf-8", "ignore"))}
                    )
                else:
                    failed_logs.append(
                        {"path": p, "exit_code": res.exit_code, "stderr": res.stderr, "cmd": cmd}
                    )

        if collected_logs:
            self._log_event(
                category=EventCategory.OS,
                description="Collected dmesg rotated files",
                data={"collected": collected_logs},
                priority=EventPriority.INFO,
            )
            self.result.message = self.result.message or "dmesg rotated files collected"

        if failed_logs:
            self._log_event(
                category=EventCategory.OS,
                description="Some dmesg files could not be collected.",
                data={"failed": failed_logs},
                priority=EventPriority.WARNING,
            )

    def _get_dmesg_content(self) -> str:
        """run dmesg command on system and return output

        Returns:
            str: dmesg output
        """

        self.logger.info("Running dmesg command on system")
        res = self._run_sut_cmd(self.DMESG_CMD, sudo=True, log_artifact=False)
        if res.exit_code != 0:
            self._log_event(
                category=EventCategory.OS,
                description="Error reading dmesg",
                data={"command": res.command, "exit_code": res.exit_code},
                priority=EventPriority.ERROR,
                console_log=True,
            )
        return res.stdout

    def collect_data(
        self,
        args: Optional[DmesgCollectorArgs] = None,
    ) -> tuple[TaskResult, DmesgData | None]:
        """Collect dmesg data from the system

        Returns:
            tuple[TaskResult, DmesgData | None]: tuple containing the result of the task and the dmesg data if available
        """
        if args is None:
            args = DmesgCollectorArgs()

        if args.skip_sudo:
            self.result.message = "Skipping sudo plugin"
            self.result.status = ExecutionStatus.NOT_RAN
            return self.result, None

        dmesg_content = self._get_dmesg_content()
        if args.collect_rotated_logs:
            self._collect_dmesg_rotations()

        if dmesg_content:
            dmesg_data = DmesgData(dmesg_content=dmesg_content)
            self.result.message = "Dmesg data collected"
            return self.result, dmesg_data

        return self.result, None
