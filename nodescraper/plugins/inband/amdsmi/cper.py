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

import io
from datetime import datetime
from typing import Dict, Optional

from nodescraper.enums import EventCategory, EventPriority


class CperAnalysisTaskMixin:
    def analyzer_cpers(
        self,
        cper_data: Dict[str, io.BytesIO],
        analysis_range_start: Optional[datetime],
        analysis_range_end: Optional[datetime],
    ):
        """Generate Events from CPER data.

        Note: CPER analysis is not currently implemented. This is a stub that logs
        a warning when CPER data is present.

        Args:
            cper_data (Dict[str, io.BytesIO]): Dictionary of CPER file names to file contents
            analysis_range_start (Optional[datetime]): Optional start time for analysis range
            analysis_range_end (Optional[datetime]): Optional end time for analysis range
        """
        # check the self._log_event method is defined
        if not hasattr(self, "_log_event") or not callable(self._log_event):
            raise NotImplementedError("The class must implement the _log_event method.")

        if cper_data:
            self._log_event(
                category=EventCategory.RAS,
                priority=EventPriority.WARNING,
                description="CPER data found but analysis is not implemented",
                data={
                    "cper_file_count": len(cper_data),
                    "cper_files": list(cper_data.keys()),
                    "note": "CPER analysis requires additional dependencies not currently available",
                },
            )
