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
import os
from pathlib import Path
from typing import Union

from pydantic import Field

from nodescraper.models import DataModel
from nodescraper.utils import get_unique_filename


class RegexSearchData(DataModel):
    """Loaded file or directory contents passed to the analyzer (via --data)."""

    content: str
    data_root: str = ""
    files: dict[str, str] = Field(default_factory=dict)

    def log_model(self, log_path: str) -> None:
        """Persist the aggregated text payload as one log file under the given base path.

        Args:
            log_path: Directory where the log file should be written.

        Returns:
            None.
        """
        log_name = os.path.join(log_path, get_unique_filename(log_path, "regex_search_source.log"))
        with open(log_name, "w", encoding="utf-8") as log_file:
            log_file.write(self.content)

    @classmethod
    def import_model(cls, model_input: Union[dict, str]) -> "RegexSearchData":
        """Import datamodel.

        Args:
            model_input: Keyed fields for direct validation, or a path string to load from disk.

        Returns:
            Instance with content, root path, and per-file bodies filled in.
        """
        if isinstance(model_input, dict):
            return cls.model_validate(model_input)
        if isinstance(model_input, str):
            return cls._from_filesystem_path(model_input)
        raise ValueError("Invalid input for regex search data")

    @classmethod
    def _from_filesystem_path(cls, path: str) -> "RegexSearchData":
        """Read one file or every file under a directory into a merged view plus a path-to-text map.

        Args:
            path: Absolute or resolvable path to a file or directory.

        Returns:
            Instance built from the read text and discovered relative paths.

        """
        path = os.path.abspath(path)
        if not os.path.exists(path):
            raise FileNotFoundError(f"Path not found: {path}")
        if os.path.isfile(path):
            text = Path(path).read_text(encoding="utf-8", errors="replace")
            rel = os.path.basename(path)
            data_root = os.path.dirname(path) or os.path.abspath(os.path.curdir)
            return cls(content=text, data_root=data_root, files={rel: text})
        if os.path.isdir(path):
            files: dict[str, str] = {}
            parts: list[str] = []
            for root, _dirs, filenames in os.walk(path):
                for name in sorted(filenames):
                    fp = os.path.join(root, name)
                    if not os.path.isfile(fp):
                        continue
                    rel = os.path.relpath(fp, path)
                    try:
                        text = Path(fp).read_text(encoding="utf-8", errors="replace")
                    except OSError:
                        continue
                    files[rel] = text
                    parts.append(f"===== {rel} =====\n{text}")
            return cls(content="\n".join(parts), data_root=path, files=files)
        raise ValueError(f"Unsupported path type: {path}")
