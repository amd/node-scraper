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
"""Fluent Redfish path builder with pathlib-like / syntax and optional parameter substitution."""
from __future__ import annotations

from typing import Dict


class RedfishPath:
    """Fluent interface for building Redfish URI paths."""

    def __init__(self, base: str = "") -> None:
        self._path = (base or "").strip().strip("/")
        self._params: Dict[str, str] = {}

    def __truediv__(self, segment: str) -> RedfishPath:
        """Allow path / \"segment\" syntax. Leading/trailing slashes on segment are stripped."""
        seg = (segment or "").strip().strip("/")
        if not seg:
            return RedfishPath(self._path)
        new_path = RedfishPath()
        new_path._path = f"{self._path}/{seg}" if self._path else seg
        new_path._params = dict(self._params)
        return new_path

    def __call__(self, **params: str) -> str:
        """Substitute placeholders in the path and return the final path string.

        Placeholders use {key}; e.g. path \"Systems/{id}/LogServices/DiagLogs\" with (id=\"UBB\")
        returns \"Systems/UBB/LogServices/DiagLogs\".
        """
        result = self._path
        for key, value in params.items():
            result = result.replace(f"{{{key}}}", value)
        return result

    def __str__(self) -> str:
        return self._path
