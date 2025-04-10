from errorscraper.base import InBandDataPlugin

from .analyzer_args import DmesgAnalyzerArgs
from .dmesg_analyzer import DmesgAnalyzer
from .dmesg_collector import DmesgCollector
from .dmesgdata import DmesgData


class DmesgPlugin(InBandDataPlugin[DmesgData, None, DmesgAnalyzerArgs]):
    """Plugin for collection and analysis of dmesg data"""

    DATA_MODEL = DmesgData

    COLLECTOR = DmesgCollector

    ANALYZER = DmesgAnalyzer
