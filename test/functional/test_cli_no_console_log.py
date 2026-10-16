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

import subprocess
import sys


def test_no_console_log_with_log_path_none_still_parses():
    """--log-path None + --no-console-log defaults to ./scraper_logs_* (no argparse error)."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "nodescraper.cli.cli",
            "--log-path",
            "None",
            "--no-console-log",
            "run-plugins",
            "OsPlugin",
            "-h",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    combined = (result.stdout or "") + (result.stderr or "")
    assert "no-console-log requires" not in combined.lower()
