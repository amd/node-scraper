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
from typing import Optional, cast

from nodescraper.enums import EventCategory, EventPriority, ExecutionStatus
from nodescraper.interfaces import DataAnalyzer
from nodescraper.models import TaskResult

from .analyzer_args import SysSettingsAnalyzerArgs
from .sys_settings_data import SysSettingsDataModel


def _get_actual_for_path(data: SysSettingsDataModel, path: str) -> Optional[str]:
    """Return the actual value from the data model for the given sysfs path.

    Args:
        data: Collected sysfs readings (path -> value).
        path: Sysfs path (with or without trailing slash).

    Returns:
        Normalized value for that path, or None if not present.
    """
    value = data.readings.get(path) or data.readings.get(path.rstrip("/"))
    return (value or "").strip().lower() if value is not None else None


class SysSettingsAnalyzer(DataAnalyzer[SysSettingsDataModel, SysSettingsAnalyzerArgs]):
    """Check sysfs settings against expected values from the checks list."""

    DATA_MODEL = SysSettingsDataModel

    def analyze_data(
        self, data: SysSettingsDataModel, args: Optional[SysSettingsAnalyzerArgs] = None
    ) -> TaskResult:
        """Compare sysfs data to expected settings from args.checks.

        Args:
            data: Collected sysfs readings to check.
            args: Analyzer args with checks (path, expected, name). If None or no checks, returns OK.

        Returns:
            TaskResult with status OK if all checks pass, ERROR if any mismatch or missing path.
        """
        mismatches = {}

        if not args or not args.checks:
            self.result.status = ExecutionStatus.OK
            self.result.message = "No checks configured."
            return self.result

        for check in args.checks:
            actual = _get_actual_for_path(data, check.path)
            if actual is None:
                mismatches[check.name] = {
                    "path": check.path,
                    "expected": check.expected,
                    "actual": None,
                    "reason": "path not collected by this plugin",
                }
                continue

            if not check.expected:
                continue
            expected_normalized = [e.strip().lower() for e in check.expected]
            if actual not in expected_normalized:
                raw = data.readings.get(check.path) or data.readings.get(check.path.rstrip("/"))
                mismatches[check.name] = {
                    "path": check.path,
                    "expected": check.expected,
                    "actual": raw,
                }

        if mismatches:
            self.result.status = ExecutionStatus.ERROR
            parts = []
            for name, info in mismatches.items():
                path = info.get("path", "")
                expected = info.get("expected")
                actual = cast(Optional[str], info.get("actual"))
                reason = info.get("reason")
                if reason:
                    part = f"{name} ({path})"
                else:
                    part = f"{name} ({path}): expected one of {expected}, actual {repr(actual)}"
                parts.append(part)
            self.result.message = "Sysfs mismatch: " + "; ".join(parts)
            self._log_event(
                category=EventCategory.OS,
                description="Sysfs mismatch detected",
                data=mismatches,
                priority=EventPriority.ERROR,
                console_log=True,
            )
        else:
            self._log_event(
                category=EventCategory.OS,
                description="Sysfs settings match expected",
                priority=EventPriority.INFO,
                console_log=True,
            )
            self.result.status = ExecutionStatus.OK
            self.result.message = "Sysfs settings as expected."

        return self.result
