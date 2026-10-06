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

from pydantic import Field

from nodescraper.models import CollectorArgs


class RegisterDecodeCollectorArgs(CollectorArgs):
    """Arguments passed through to the register tool collect entry point."""

    tool_group: Optional[str] = Field(
        default=None,
        description="Entry-point group used to discover the register tool.",
    )
    tool_name: Optional[str] = Field(
        default=None,
        description=(
            "Optional entry-point name within tool_group. Required only when more "
            "than one register tool is installed."
        ),
    )
    threads: Optional[list[int]] = Field(
        default=None,
        description="Logical CPU indices to scan. Omit to scan every online CPU.",
    )
    banks: Optional[list[int]] = Field(
        default=None,
        description="Register bank indices to scan. Omit to scan every bank.",
    )
    verbose: bool = Field(
        default=False,
        description="Ask the register tool to emit scan diagnostics.",
    )
    capture_all: bool = Field(
        default=False,
        description="Keep banks that do not have a pending error.",
    )
