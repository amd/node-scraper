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
from pydantic import Field

from nodescraper.models import AnalyzerArgs


class RedfishInventoryAnalyzerArgs(AnalyzerArgs):
    """Analyzer args for comparing Redfish firmware inventory across targets."""

    compare_firmware: bool = Field(
        default=True,
        description=(
            "Compare FirmwareInventory across this plugin's connected targets. "
            "Default true. A different Version, a member missing on a connected target, "
            "or a missing Version (recorded as N/A) logs one FW warning per component. "
            "The warning records Version, Status Health, Status State, SoftwareId, "
            "Updateable, and Oem SVN. Ids are compared as published. "
            "One connected target, a failed connection, or false skips the comparison. "
            "--data loads one model and does not compare nodes."
        ),
    )
