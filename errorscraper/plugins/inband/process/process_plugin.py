from errorscraper.base import InBandDataPlugin

from .analyzer_args import ProcessAnalyzerArgs
from .collector_args import ProcessCollectorArgs
from .process_analyzer import ProcessAnalyzer
from .process_collector import ProcessCollector
from .processdata import ProcessDataModel


class ProcessPlugin(InBandDataPlugin[ProcessDataModel, ProcessCollectorArgs, ProcessAnalyzerArgs]):
    """Plugin for collection and analysis of process data"""

    DATA_MODEL = ProcessDataModel

    COLLECTOR = ProcessCollector

    ANALYZER = ProcessAnalyzer
