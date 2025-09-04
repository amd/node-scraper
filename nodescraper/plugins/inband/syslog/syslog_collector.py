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
from nodescraper.connection.inband.inband import TextFileArtifact
from nodescraper.enums import EventCategory, EventPriority, OSFamily
from nodescraper.models import TaskResult
from nodescraper.utils import nice_rotated_name, shell_quote

from .syslogdata import SyslogData


class SyslogCollector(InBandDataCollector[SyslogData, None]):
    """Read syslog log"""

    SUPPORTED_OS_FAMILY = {OSFamily.LINUX}

    DATA_MODEL = SyslogData

    SYSLOG_CMD = r"ls -1 /var/log/syslog* 2>/dev/null | grep -E '^/var/log/syslog(\.[0-9]+(\.gz)?)?$' || true"

    def _collect_syslog_rotations(self) -> list[TextFileArtifact]:
        ret = []
        list_res = self._run_sut_cmd(self.SYSLOG_CMD, sudo=True)
        paths = [p.strip() for p in (list_res.stdout or "").splitlines() if p.strip()]
        if not paths:
            self._log_event(
                category=EventCategory.OS,
                description="No /var/log/syslog files found (including rotations).",
                data={"list_exit_code": list_res.exit_code},
                priority=EventPriority.WARNING,
            )
            return []

        collected_logs, failed_logs = [], []
        collected = []
        for p in paths:
            qp = shell_quote(p)
            if p.endswith(".gz"):
                cmd = f"gzip -dc {qp} 2>/dev/null || zcat {qp} 2>/dev/null"
                res = self._run_sut_cmd(cmd, sudo=True, log_artifact=False)
                if res.exit_code == 0 and res.stdout is not None:
                    fname = nice_rotated_name(p, "syslog")
                    self.logger.info("Collected syslog log: %s", fname)
                    collected.append(TextFileArtifact(filename=fname, contents=res.stdout))
                    collected_logs.append(fname)
                else:
                    failed_logs.append(p)
            else:
                cmd = f"cat {qp}"
                res = self._run_sut_cmd(cmd, sudo=True, log_artifact=False)
                if res.exit_code == 0 and res.stdout is not None:
                    fname = nice_rotated_name(p, "syslog")
                    self.logger.info("Collected syslog log: %s", fname)
                    collected_logs.append(fname)
                    collected.append(TextFileArtifact(filename=fname, contents=res.stdout))
                else:
                    failed_logs.append(p)

        if collected_logs:
            self._log_event(
                category=EventCategory.OS,
                description="Collected syslog rotated files",
                data={"collected": collected_logs},
                priority=EventPriority.INFO,
            )
            self.result.message = self.result.message or "syslog rotated files collected"

        if failed_logs:
            self._log_event(
                category=EventCategory.OS,
                description="Some syslog files could not be collected.",
                data={"failed": failed_logs},
                priority=EventPriority.WARNING,
            )

        if collected:
            ret = collected
        return ret

    def collect_data(
        self,
        args=None,
    ) -> tuple[TaskResult, SyslogData | None]:
        """Collect syslog data from the system

        Returns:
            tuple[TaskResult | None]: tuple containing the result of the task and the syslog data if available
        """
        syslog_logs = self._collect_syslog_rotations()

        if syslog_logs:
            syslog_data = SyslogData(syslog_logs=syslog_logs)
            self.result.message = "Syslog data collected"
            return self.result, syslog_data

        return self.result, None
