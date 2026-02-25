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
import logging
import os
from typing import Optional, Tuple

from .dmesg_plugin import DmesgPlugin
from .dmesgdata import DmesgData


def find_dmesg_datamodel_path(run_path: str) -> Optional[str]:
    """Find the DmesgPlugin collector datamodel under a scraper run directory."""
    return DmesgPlugin.find_datamodel_path_in_run(run_path)


def load_dmesg_data(path: str) -> Tuple[Optional[DmesgData], Optional[str]]:
    """Load DmesgData from a scraper run directory or a datamodel file path."""
    path = os.path.abspath(path)
    if not os.path.exists(path):
        return None, None
    dm_path = path if os.path.isfile(path) else DmesgPlugin.find_datamodel_path_in_run(path)
    if not dm_path:
        return None, None
    dm = DmesgPlugin.load_datamodel_from_path(dm_path)
    return (dm, dm_path) if dm is not None else (None, None)


def compute_extracted_errors(dm: DmesgData) -> list[str]:
    """Apply DmesgPlugin analyzer regexes to dmesg content (in memory only)."""
    out = DmesgPlugin.get_extracted_errors(dm)
    return out if out is not None else []


def compare_dmesg_runs(
    path1: str,
    path2: str,
    logger: Optional[logging.Logger] = None,
) -> Tuple[list[str], list[str], str, str]:
    """Load two DmesgPlugin runs, compute extracted errors in memory, and compare."""
    log = logger or logging.getLogger(__name__)
    label1 = os.path.basename(path1.rstrip(os.sep))
    label2 = os.path.basename(path2.rstrip(os.sep))

    d1 = DmesgPlugin.load_run_data(path1)
    d2 = DmesgPlugin.load_run_data(path2)

    if d1 is None:
        log.warning("No DmesgPlugin datamodel found at: %s", path1)
        return [], [], label1, label2
    if d2 is None:
        log.warning("No DmesgPlugin datamodel found at: %s", path2)
        return [], [], label1, label2

    err1 = set(d1.get("extracted_errors") or [])
    err2 = set(d2.get("extracted_errors") or [])
    only_in_1 = sorted(err1 - err2)
    only_in_2 = sorted(err2 - err1)

    return only_in_1, only_in_2, label1, label2
