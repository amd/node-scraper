from errorscraper.base import InBandDataPlugin

from .analyzer_args import KernelAnalyzerArgs
from .kernel_analyzer import KernelAnalyzer
from .kernel_collector import KernelCollector
from .kerneldata import KernelDataModel


class KernelPlugin(InBandDataPlugin[KernelDataModel, None, KernelAnalyzerArgs]):
    """Plugin for collection and analysis of kernel data"""

    DATA_MODEL = KernelDataModel

    COLLECTOR = KernelCollector

    ANALYZER = KernelAnalyzer
