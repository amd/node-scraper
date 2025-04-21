from errorscraper.base import InBandDataPlugin

from .analyzer_args import StorageAnalyzerArgs
from .storage_analyzer import StorageAnalyzer
from .storage_collector import StorageCollector
from .storagedata import StorageDataModel


class StoragePlugin(InBandDataPlugin[StorageDataModel, None, StorageAnalyzerArgs]):
    """Plugin for collection and analysis of disk usage data"""

    DATA_MODEL = StorageDataModel

    COLLECTOR = StorageCollector

    ANALYZER = StorageAnalyzer
