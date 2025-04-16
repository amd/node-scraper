from errorscraper.base import InBandDataPlugin

from .analyzer_args import OsAnalyzerArgs
from .os_analyzer import OsAnalyzer
from .os_collector import OsCollector
from .osdata import OsDataModel


class OsPlugin(InBandDataPlugin[OsDataModel, None, OsAnalyzerArgs]):
    """Plugin for collection and analysis of os version data"""

    DATA_MODEL = OsDataModel

    COLLECTOR = OsCollector

    ANALYZER = OsAnalyzer
