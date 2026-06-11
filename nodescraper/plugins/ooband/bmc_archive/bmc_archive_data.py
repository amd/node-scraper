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
from typing import Optional

from pydantic import Field

from nodescraper.connection.inband.inband import BinaryFileArtifact
from nodescraper.models import DataModel


class ArchiveCollectionResult(DataModel):
    """Result of archiving one BMC path."""

    name: str
    path: str
    success: bool = False
    skipped: bool = False
    exit_code: int = 0
    stderr: str = ""
    size_bytes: int = 0
    archive_filename: Optional[str] = None


class BmcArchiveDataModel(DataModel):
    """Collected BMC directory archives."""

    results: list[ArchiveCollectionResult] = Field(default_factory=list)
    archives: list[BinaryFileArtifact] = Field(default_factory=list)

    def log_model(self, log_path: str) -> None:
        for archive in self.archives:
            archive.log_model(log_path)

        log_name = os.path.join(log_path, "oob_bmc_archive_results.json")
        with open(log_name, "w", encoding="utf-8") as log_file:
            log_file.write(
                self.model_dump_json(
                    indent=2,
                    exclude={"archives"},
                )
            )
