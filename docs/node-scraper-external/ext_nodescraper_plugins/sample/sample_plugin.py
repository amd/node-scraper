from nodescraper.base import InBandDataPlugin

from .sample_analyzer import SampleAnalyzer
from .sample_collector import SampleCollector
from .sample_data import SampleDataModel


class SamplePlugin(InBandDataPlugin[SampleDataModel, None, None]):
    """Example external plugin."""

    DATA_MODEL = SampleDataModel

    COLLECTOR = SampleCollector

    ANALYZER = SampleAnalyzer
