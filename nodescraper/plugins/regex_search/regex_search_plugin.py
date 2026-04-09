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
from nodescraper.connection.inband import InBandConnectionManager, SSHConnectionParams
from nodescraper.interfaces import DataPlugin
from nodescraper.models import CollectorArgs

from .analyzer_args import RegexSearchAnalyzerArgs
from .regex_search_analyzer import RegexSearchAnalyzer
from .regex_search_data import RegexSearchData


class RegexSearchPlugin(
    DataPlugin[
        InBandConnectionManager,
        SSHConnectionParams,
        RegexSearchData,
        CollectorArgs,
        RegexSearchAnalyzerArgs,
    ]
):
    """Analyzer-only plugin: search user regexes against a file or directory (--data)."""

    DATA_MODEL = RegexSearchData
    ANALYZER = RegexSearchAnalyzer
