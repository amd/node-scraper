from errorscraper.base import InBandDataPlugin

from .analyzer_args import RocmAnalyzerArgs
from .rocm_analyzer import RocmAnalyzer
from .rocm_collector import RocmCollector
from .rocmdata import RocmDataModel


class RocmPlugin(InBandDataPlugin[RocmDataModel, None, RocmAnalyzerArgs]):
    """Plugin for collection and analysis of rocm version data"""

    DATA_MODEL = RocmDataModel

    COLLECTOR = RocmCollector

    ANALYZER = RocmAnalyzer
