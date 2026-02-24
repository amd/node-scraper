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
import re
from typing import Optional

from nodescraper.base import InBandDataCollector
from nodescraper.enums import EventCategory, EventPriority, ExecutionStatus, OSFamily
from nodescraper.models import TaskResult

from .thpdata import ThpDataModel

THP_BASE = "/sys/kernel/mm/transparent_hugepage"
# Sysfs format: "[always] madvise never" -> extract bracketed value
BRACKETED_RE = re.compile(r"\[(\w+)\]")


def _parse_bracketed_setting(content: str) -> Optional[str]:
    """Extract the active setting from sysfs content (value in square brackets)."""
    if not content:
        return None
    match = BRACKETED_RE.search(content.strip())
    return match.group(1).strip() if match else None


class ThpCollector(InBandDataCollector[ThpDataModel, None]):
    """Collect transparent huge pages (THP) settings from sysfs."""

    DATA_MODEL = ThpDataModel
    SUPPORTED_OS_FAMILY: set[OSFamily] = {OSFamily.LINUX}

    # Command template for doc generator: {} is each sysfs path (e.g. from checks).
    CMD = "cat {}"
    CMD_ENABLED = f"cat {THP_BASE}/enabled"
    CMD_DEFRAG = f"cat {THP_BASE}/defrag"

    def collect_data(self, args=None) -> tuple[TaskResult, Optional[ThpDataModel]]:
        """Collect THP enabled and defrag settings from the system."""
        if self.system_info.os_family != OSFamily.LINUX:
            self._log_event(
                category=EventCategory.OS,
                description="THP collection is only supported on Linux.",
                priority=EventPriority.WARNING,
                console_log=True,
            )
            return self.result, None

        enabled_raw = self._run_sut_cmd(self.CMD_ENABLED)
        defrag_raw = self._run_sut_cmd(self.CMD_DEFRAG)

        enabled: Optional[str] = None
        defrag: Optional[str] = None

        if enabled_raw.exit_code == 0 and enabled_raw.stdout:
            enabled = _parse_bracketed_setting(enabled_raw.stdout)
        else:
            self._log_event(
                category=EventCategory.OS,
                description="Failed to read THP enabled setting",
                data={"exit_code": enabled_raw.exit_code},
                priority=EventPriority.WARNING,
                console_log=True,
            )

        if defrag_raw.exit_code == 0 and defrag_raw.stdout:
            defrag = _parse_bracketed_setting(defrag_raw.stdout)
        else:
            self._log_event(
                category=EventCategory.OS,
                description="Failed to read THP defrag setting",
                data={"exit_code": defrag_raw.exit_code},
                priority=EventPriority.WARNING,
                console_log=True,
            )

        if enabled is None and defrag is None:
            self.result.message = "THP settings not read"
            self.result.status = ExecutionStatus.ERROR
            return self.result, None

        thp_data = ThpDataModel(enabled=enabled, defrag=defrag)
        self._log_event(
            category=EventCategory.OS,
            description="THP settings collected",
            data=thp_data.model_dump(),
            priority=EventPriority.INFO,
        )
        self.result.message = f"THP enabled={enabled}, defrag={defrag}"
        self.result.status = ExecutionStatus.OK
        return self.result, thp_data
