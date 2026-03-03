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

from pydantic import BaseModel, Field

from nodescraper.models import AnalyzerArgs


class SysfsCheck(BaseModel):
    """One sysfs check: path to read, acceptable values or pattern, and display name.

    For file paths: use expected (list of acceptable values); if empty, check passes.
    For directory paths: use pattern (regex); at least one directory entry must match (e.g. ^hsn[0-9]+).
    """

    path: str
    expected: list[str] = Field(default_factory=list)
    name: str
    pattern: Optional[str] = None


class SysSettingsAnalyzerArgs(AnalyzerArgs):
    """Sysfs settings for analysis via a list of checks (path, expected values, name).

    The path in each check is the sysfs path to read; the collector uses these paths
    when collection_args is derived from analysis_args (e.g. by the plugin).
    """

    checks: Optional[list[SysfsCheck]] = None

    def paths_to_collect(self) -> list[str]:
        """Return unique sysfs file paths from checks (those without pattern), for use by the collector."""
        if not self.checks:
            return []
        seen = set()
        out = []
        for c in self.checks:
            if c.pattern:
                continue
            p = c.path.rstrip("/")
            if p not in seen:
                seen.add(p)
                out.append(c.path)
        return out

    def paths_to_list(self) -> list[str]:
        """Return unique sysfs directory paths from checks (those with pattern), for listing (ls)."""
        if not self.checks:
            return []
        seen = set()
        out = []
        for c in self.checks:
            if not c.pattern:
                continue
            p = c.path.rstrip("/")
            if p not in seen:
                seen.add(p)
                out.append(c.path)
        return out
