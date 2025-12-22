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
from typing import Optional, Union

from pydantic import BaseModel

from nodescraper.enums import ExecutionStatus


class PluginResult(BaseModel):
    """Object for result of a plugin"""

    status: ExecutionStatus
    source: str
    message: Optional[str] = None
    result_data: Optional[Union[dict, BaseModel]] = None

    def get_system_data(self):
        """Get the collected system data if available.

        Returns:
            DataModel or None: The system data collected by the plugin, or None if not available.
        """
        if self.result_data is not None and hasattr(self.result_data, "system_data"):
            return self.result_data.system_data  # type: ignore[union-attr]
        return None

    def get_analysis_events(self) -> list:
        """Get analysis events/matches if available.

        Returns:
            list[Event]: List of analysis events, or empty list if not available.
        """
        if self.result_data is not None and hasattr(self.result_data, "analysis_result"):
            analysis_result = self.result_data.analysis_result  # type: ignore[union-attr]
            if hasattr(analysis_result, "events"):
                return analysis_result.events  # type: ignore[union-attr]
        return []

    def get_artifact_files(self) -> list[str]:
        """Get all artifact file paths written by this plugin.

        Returns:
            list[str]: List of absolute file paths to artifacts created by the plugin.
        """
        files = []
        if self.result_data is not None:
            if hasattr(self.result_data, "collection_result"):
                collection_result = self.result_data.collection_result  # type: ignore[union-attr]
                if hasattr(collection_result, "artifact_file_paths"):
                    files.extend(collection_result.artifact_file_paths)  # type: ignore[union-attr]
            if hasattr(self.result_data, "analysis_result"):
                analysis_result = self.result_data.analysis_result  # type: ignore[union-attr]
                if hasattr(analysis_result, "artifact_file_paths"):
                    files.extend(analysis_result.artifact_file_paths)  # type: ignore[union-attr]
        return files
