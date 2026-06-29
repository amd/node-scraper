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
from nodescraper.base import InBandDataPlugin

from .analyzer_args import ScaleOutDellAnalyzerArgs
from .collector_args import ScaleOutDellCollectorArgs
from .scale_out_dell_analyzer import ScaleOutDellAnalyzer
from .scale_out_dell_collector import ScaleOutDellCollector
from .scaleoutdelldata import ScaleOutDellDataModel


class ScaleOutDellPlugin(
    InBandDataPlugin[ScaleOutDellDataModel, ScaleOutDellCollectorArgs, ScaleOutDellAnalyzerArgs]
):
    """Plugin for collection and analysis of Dell SONiC switch data"""

    DATA_MODEL = ScaleOutDellDataModel

    COLLECTOR = ScaleOutDellCollector

    COLLECTOR_ARGS = ScaleOutDellCollectorArgs

    ANALYZER = ScaleOutDellAnalyzer

    ANALYZER_ARGS = ScaleOutDellAnalyzerArgs
