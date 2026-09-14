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
from __future__ import annotations

from pathlib import Path
from typing import Optional

DEFAULT_AFID_SAG_PATH = "/opt/amd/afid/AFID_SAG.json"


def default_afid_sag_path() -> str:
    """Return the default AFID_SAG.json path when analysis_args does not override it."""
    return DEFAULT_AFID_SAG_PATH


def resolve_configured_afid_sag_path(configured_path: Optional[str]) -> str:
    """Resolve AFID SAG path from analysis_args or the built-in default."""
    if configured_path is not None and str(configured_path).strip():
        return str(configured_path).strip()
    return default_afid_sag_path()


def validate_afid_sag_path(path: str) -> str:
    """Return path when the AFID SAG file exists, otherwise raise HubRunError."""
    from .se_runner import HubRunError

    sag_path = Path(path)
    if not sag_path.is_file():
        raise HubRunError(f"AFID SAG file not found: {path}")
    return path
