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

from .collector_args import SysSettingsCollectorArgs
from .sys_settings_data import SysSettingsDataModel

# Sysfs format: "[always] madvise never" -> extract bracketed value
BRACKETED_RE = re.compile(r"\[(\w+)\]")


def _parse_bracketed_setting(content: str) -> Optional[str]:
    """Extract the active setting from sysfs content (value in square brackets).

    Args:
        content: Raw sysfs file content (e.g. "[always] madvise never").

    Returns:
        The bracketed value if present, else None.
    """
    if not content:
        return None
    match = BRACKETED_RE.search(content.strip())
    return match.group(1).strip() if match else None


def _paths_from_args(args: Optional[SysSettingsCollectorArgs]) -> list[str]:
    """Extract list of sysfs paths from collection args.

    Args:
        args: Collector args containing paths to read, or None.

    Returns:
        List of sysfs paths; empty if args is None or args.paths is empty.
    """
    if args is None:
        return []
    return list(args.paths) if args.paths else []


class SysSettingsCollector(InBandDataCollector[SysSettingsDataModel, SysSettingsCollectorArgs]):
    """Collect sysfs settings from user-specified paths (paths come from config/args)."""

    DATA_MODEL = SysSettingsDataModel
    SUPPORTED_OS_FAMILY: set[OSFamily] = {OSFamily.LINUX}

    CMD = "cat {}"

    def collect_data(
        self, args: Optional[SysSettingsCollectorArgs] = None
    ) -> tuple[TaskResult, Optional[SysSettingsDataModel]]:
        """Collect sysfs values for each path in args.paths.

        Args:
            args: Collector args with paths to read; if None or empty paths, returns NOT_RAN.

        Returns:
            Tuple of (TaskResult, SysSettingsDataModel or None). Data is None on NOT_RAN or ERROR.
        """
        if self.system_info.os_family != OSFamily.LINUX:
            self._log_event(
                category=EventCategory.OS,
                description="Sysfs collection is only supported on Linux.",
                priority=EventPriority.WARNING,
                console_log=True,
            )
            return self.result, None

        paths = _paths_from_args(args)
        if not paths:
            self.result.message = "No paths configured for sysfs collection"
            self.result.status = ExecutionStatus.NOT_RAN
            return self.result, None

        readings: dict[str, str] = {}
        for path in paths:
            res = self._run_sut_cmd(self.CMD.format(path), sudo=False)
            if res.exit_code == 0 and res.stdout:
                value = _parse_bracketed_setting(res.stdout) or res.stdout.strip()
                readings[path] = value
            else:
                self._log_event(
                    category=EventCategory.OS,
                    description=f"Failed to read sysfs path: {path}",
                    data={"exit_code": res.exit_code},
                    priority=EventPriority.WARNING,
                    console_log=True,
                )

        if not readings:
            self.result.message = "Sysfs settings not read"
            self.result.status = ExecutionStatus.ERROR
            return self.result, None

        sys_settings_data = SysSettingsDataModel(readings=readings)
        self._log_event(
            category=EventCategory.OS,
            description="Sysfs settings collected",
            data=sys_settings_data.model_dump(),
            priority=EventPriority.INFO,
        )
        self.result.message = f"Sysfs collected {len(readings)} path(s)"
        self.result.status = ExecutionStatus.OK
        return self.result, sys_settings_data
