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
"""Shared plugin wiring for in-band and OOB generic command collection plugins."""

from typing import Optional, Type

from nodescraper.interfaces.dataanalyzertask import DataAnalyzer
from nodescraper.interfaces.dataplugin import CollectorArgsClasses, CollectorClasses
from nodescraper.models import AnalyzerArgs

from .analyzer_args import GenericAnalyzerArgs
from .collector_args import GenericCollectionCollectorArgs
from .generic_analyzer import GenericAnalyzer
from .generic_collection_collector import GenericCollectionCollector
from .generic_collection_data import GenericCollectionDataModel


class GenericCollectionPluginMixin:
    """Collector, analyzer, and args shared by GenericCollectionPlugin variants."""

    DATA_MODEL: Type[GenericCollectionDataModel] = GenericCollectionDataModel

    COLLECTOR: Optional[CollectorClasses] = GenericCollectionCollector

    COLLECTOR_ARGS: Optional[CollectorArgsClasses] = GenericCollectionCollectorArgs

    ANALYZER: Optional[Type[DataAnalyzer]] = GenericAnalyzer

    ANALYZER_ARGS: Optional[Type[AnalyzerArgs]] = GenericAnalyzerArgs
