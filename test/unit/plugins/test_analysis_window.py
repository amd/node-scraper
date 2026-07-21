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
from nodescraper.plugins.serviceability.analysis_window import (
    analyze_serviceability_window,
)
from nodescraper.plugins.serviceability.analyzer_args import ServiceabilityAnalyzerArgs
from nodescraper.plugins.serviceability.serviceability_data import (
    ServiceabilityDataModel,
)


def test_analyze_serviceability_window_skip_hub():
    data = ServiceabilityDataModel(
        rf_events=[
            {
                "MessageId": "X",
                "Message": "fail",
                "Severity": "Critical",
                "Created": "2026-01-01T00:00:00Z",
                "Afid": 1,
                "serviceable_unit": "GPU0",
            }
        ]
    )
    result = analyze_serviceability_window(
        data,
        ServiceabilityAnalyzerArgs(skip_hub=True),
    )
    assert result.ok is True
    assert result.serviceability is not None
    assert len(result.afid_events) == 1
