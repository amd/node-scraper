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


class RedfishEventLogCollectorArgs(CollectorArgs):
    """Collector args for reading a Redfish LogService's Entries collection."""

    log_service_path: str = Field(
        default="redfish/v1/Systems/system/LogServices/EventLog",
        description="Redfish path to the LogService; entries are read from <log_service_path>/Entries.",
    )
    max_entries: Optional[int] = Field(
        default=None,
        ge=1,
        description="Keep only the newest N entries (by Created). All pages are still read.",
    )
    max_pages: int = Field(
        default=100,
        ge=1,
        le=10000,
        description="Safety cap on the number of $skip pages requested.",
    )
    clear_logs_after_collection: bool = Field(
        default=False,
        description=(
            "If True, POST LogService.ClearLog to log_service_path after a successful "
            "collection. Requires system_interaction_level >= INTERACTIVE."
        ),
    )
