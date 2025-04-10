from errorscraper.base import InBandDataPlugin

from .analyzer_args import DkmsAnalyzerArgs
from .dkms_analyzer import DkmsAnalyzer
from .dkms_collector import DkmsCollector
from .dkmsdata import DkmsDataModel


class DkmsPlugin(InBandDataPlugin[DkmsDataModel, None, DkmsAnalyzerArgs]):
    """Plugin for collection and analysis of DKMS data"""

    DATA_MODEL = DkmsDataModel

    COLLECTOR = DkmsCollector

    ANALYZER = DkmsAnalyzer
