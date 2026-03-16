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

import importlib
import re
from pathlib import Path
from unittest.mock import patch

import pytest


def _get_project_name_from_pyproject() -> str:
    repo_root = Path(__file__).resolve().parent.parent.parent
    pyproject = repo_root / "pyproject.toml"
    content = pyproject.read_text()
    in_project = False
    for line in content.splitlines():
        if line.strip() == "[project]":
            in_project = True
            continue
        if in_project and line.strip().startswith("["):
            break
        if in_project:
            match = re.match(r'^\s*name\s*=\s*["\']([^"\']+)["\']', line)
            if match:
                return match.group(1)
    pytest.fail("Could not find name in [project] section of pyproject.toml")


def test_version_resolved_using_package_name_from_pyproject():
    expected_name = _get_project_name_from_pyproject()
    with patch("importlib.metadata.version", return_value="1.2.3") as mock_version:
        import nodescraper

        importlib.reload(nodescraper)
        assert nodescraper.__version__ == "1.2.3"
        mock_version.assert_called_once_with(
            expected_name
        ), "nodescraper.__init__ must call version() with the same name as pyproject.toml [project] name"


def test_version_unknown_when_package_not_found():
    from importlib.metadata import PackageNotFoundError

    expected_name = _get_project_name_from_pyproject()
    with patch("importlib.metadata.version", side_effect=PackageNotFoundError(expected_name)):
        import nodescraper

        importlib.reload(nodescraper)
        assert nodescraper.__version__ == "unknown"
