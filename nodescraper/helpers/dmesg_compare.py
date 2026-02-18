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
import json
import logging
import os
from typing import Optional, Tuple

from nodescraper.plugins.inband.dmesg.dmesg_analyzer import DmesgAnalyzer
from nodescraper.plugins.inband.dmesg.dmesgdata import DmesgData


def find_dmesg_datamodel_path(run_path: str) -> Optional[str]:
    """Find the DmesgPlugin collector datamodel.json under a scraper run directory.

    Args:
        run_path: Path to a scraper log run directory (e.g. scraper_logs_*).

    Returns:
        Absolute path to the datamodel.json file, or None if not found.
    """
    run_path = os.path.abspath(run_path)
    if not os.path.isdir(run_path):
        return None
    for root, _dirs, files in os.walk(run_path):
        if "collector" not in os.path.basename(root).lower():
            continue
        for f in files:
            if f.lower().endswith("datamodel.json"):
                full = os.path.join(root, f)
                try:
                    with open(full, encoding="utf-8") as fp:
                        data = json.load(fp)
                    if "dmesg_content" in data:
                        return full
                except (json.JSONDecodeError, OSError):
                    continue
    return None


def load_dmesg_data(path: str) -> Tuple[Optional[DmesgData], Optional[str]]:
    """Load DmesgData from a scraper run directory or a datamodel.json path.

    Args:
        path: Path to a scraper run directory or to a DmesgData datamodel.json file.

    Returns:
        Tuple of (DmesgData instance or None, path to the JSON file that was loaded, or None).
    """
    path = os.path.abspath(path)
    if not os.path.exists(path):
        return None, None

    if os.path.isfile(path):
        if not path.lower().endswith(".json"):
            return None, None
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            if "dmesg_content" not in data:
                return None, None
            return DmesgData(**data), path
        except (json.JSONDecodeError, OSError):
            return None, None

    datamodel_path = find_dmesg_datamodel_path(path)
    if not datamodel_path:
        return None, None
    try:
        with open(datamodel_path, encoding="utf-8") as f:
            data = json.load(f)
        return DmesgData(**data), datamodel_path
    except (json.JSONDecodeError, OSError):
        return None, None


def compute_extracted_errors(dm: DmesgData) -> list[str]:
    """Apply DmesgAnalyzer regexes to dmesg_content and return extracted errors (in memory only).

    Args:
        dm: DmesgData instance (not modified).

    Returns:
        Sorted list of error match strings.
    """
    matches = DmesgAnalyzer.get_error_matches(dm.dmesg_content)
    return sorted(matches)


def compare_dmesg_runs(
    path1: str,
    path2: str,
    logger: Optional[logging.Logger] = None,
) -> Tuple[list[str], list[str], str, str]:
    """Load two DmesgPlugin runs, compute extracted errors in memory, and compare (no disk write).

    Args:
        path1: First run directory or datamodel.json path.
        path2: Second run directory or datamodel.json path.
        logger: Optional logger for messages.

    Returns:
        Tuple of (errors_only_in_first, errors_only_in_second, label1, label2).
        If a run has no DmesgPlugin data, the corresponding list is empty and label is the path.
    """
    log = logger or logging.getLogger(__name__)
    label1 = os.path.basename(path1.rstrip(os.sep))
    label2 = os.path.basename(path2.rstrip(os.sep))

    dm1, _ = load_dmesg_data(path1)
    dm2, _ = load_dmesg_data(path2)

    if dm1 is None:
        log.warning("No DmesgPlugin datamodel found at: %s", path1)
        return [], [], label1, label2
    if dm2 is None:
        log.warning("No DmesgPlugin datamodel found at: %s", path2)
        return [], [], label1, label2

    set1 = set(compute_extracted_errors(dm1))
    set2 = set(compute_extracted_errors(dm2))
    only_in_1 = sorted(set1 - set2)
    only_in_2 = sorted(set2 - set1)

    return only_in_1, only_in_2, label1, label2
