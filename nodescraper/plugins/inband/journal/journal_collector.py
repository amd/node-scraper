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
from nodescraper.connection.inband import TextFileArtifact
from nodescraper.enums import EventCategory, EventPriority, OSFamily
from nodescraper.models import TaskResult

from .journaldata import JournalData


class JournalCollector(InBandDataCollector[JournalData, None]):
    """Read journal log via journalctl."""

    SUPPORTED_OS_FAMILY = {OSFamily.LINUX}
    DATA_MODEL = JournalData

    CMD = "ls -1 /var/log/journal/*/system* 2>/dev/null || true"

    def _shell_quote(self, s: str) -> str:
        return "'" + s.replace("'", "'\"'\"'") + "'"

    def _flat_name(self, path: str) -> str:
        return "journalctl__" + path.lstrip("/").replace("/", "__") + ".json"

    def _read_with_journalctl(self, path: str):
        qp = self._shell_quote(path)
        cmd = f"journalctl --no-pager --system --all --file={qp} --output=json"
        res = self._run_sut_cmd(cmd, sudo=True, log_artifact=False, strip=False)

        if res.exit_code == 0:
            text = (
                res.stdout.decode("utf-8", "replace")
                if isinstance(res.stdout, (bytes, bytearray))
                else res.stdout
            )
            fname = self._flat_name(path)
            self.result.artifacts.append(TextFileArtifact(filename=fname, contents=text))
            self.logger.info("Collected journal: %s", path)
            return fname

        return None

    def _get_journals(self):
        list_res = self._run_sut_cmd(self.CMD, sudo=True)
        paths = [p.strip() for p in (list_res.stdout or "").splitlines() if p.strip()]

        if not paths:
            self._log_event(
                category=EventCategory.OS,
                description="No /var/log/journal files found (including rotations).",
                data={"list_exit_code": list_res.exit_code},
                priority=EventPriority.WARNING,
            )
            return []

        collected, failed = [], []
        for p in paths:
            self.logger.debug("Reading journal file: %s", p)
            fname = self._read_with_journalctl(p)
            if fname:
                collected.append(fname)
            else:
                failed.append(fname)

        if collected:
            self._log_event(
                category=EventCategory.OS,
                description="Collected journal logs.",
                data={"collected": collected},
                priority=EventPriority.INFO,
            )
            self.result.message = self.result.message or "journalctl logs collected"

        if failed:
            self._log_event(
                category=EventCategory.OS,
                description="Some journal files could not be read with journalctl.",
                data={"failed": failed},
                priority=EventPriority.WARNING,
            )

        return collected

    def collect_data(self, args=None) -> tuple[TaskResult, JournalData | None]:
        collected = self._get_journals()
        if collected:
            data = JournalData(journal_logs=collected)
            self.result.message = self.result.message or "Journal data collected"
            return self.result, data
        return self.result, None
