from errorscraper.interfaces.inbanddataplugin import InBandDataPlugin

from .analyzer_args import BiosAnalyzerArgs
from .bios_analyzer import BiosAnalyzer
from .bios_collector import BiosCollector
from .biosdata import BiosDataModel


class BiosPlugin(InBandDataPlugin[BiosDataModel, None, BiosAnalyzerArgs]):
    """Plugin for collection and analysis of BIOS data"""

    DATA_MODEL = BiosDataModel

    COLLECTOR = BiosCollector

    ANALYZER = BiosAnalyzer
