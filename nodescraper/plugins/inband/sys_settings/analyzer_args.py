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

from pydantic import BaseModel

from nodescraper.models import AnalyzerArgs


class SysfsCheck(BaseModel):
    """One sysfs check: path to read, acceptable values, and display name.

    If expected is an empty list, the check is treated as passing (no constraint).
    """

    path: str
    expected: list[str]
    name: str


class SysSettingsAnalyzerArgs(AnalyzerArgs):
    """Sysfs settings for analysis via a list of checks (path, expected values, name).

    The path in each check is the sysfs path to read; the collector uses these paths
    when collection_args is derived from analysis_args (e.g. by the plugin).
    """

    checks: Optional[list[SysfsCheck]] = None

    def paths_to_collect(self) -> list[str]:
        """Return the unique sysfs paths from checks, for use by the collector.

        Returns:
            List of unique path strings from self.checks, preserving order of first occurrence.
        """
        if not self.checks:
            return []
        seen = set()
        out = []
        for c in self.checks:
            p = c.path.rstrip("/")
            if p not in seen:
                seen.add(p)
                out.append(c.path)
        return out
