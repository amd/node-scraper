from errorscraper.base import InBandDataPlugin

from .analyzer_args import MemoryAnalyzerArgs
from .memory_analyzer import MemoryAnalyzer
from .memory_collector import MemoryCollector
from .memorydata import MemoryDataModel


class MemoryPlugin(InBandDataPlugin[MemoryDataModel, None, MemoryAnalyzerArgs]):
    """Plugin for collection and analysis of memory data"""

    DATA_MODEL = MemoryDataModel

    COLLECTOR = MemoryCollector

    ANALYZER = MemoryAnalyzer
